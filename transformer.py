"""Transformer - Hyperspectral to netCDF
"""

import argparse
import json
import logging
import os
import subprocess
from typing import Optional
import numpy as np
import psutil
from netCDF4 import Dataset
import spectral.io.envi as envi

import transformer_class

CALIB_ROOT = "/home/extractor"


class __internal__():
    """Class for internal use only functions
    """

    def __init__(self):
        """Initializes class instance
        """

    @staticmethod
    def get_needed_files(source_files: list) -> tuple:
        """Fetches the names of the needed files
        Arguments:
            source_files: a list of file names to look through
        Return:
            Returns a tuple consisting of the raw file name. If the name of
            a file is not found, None is returned in its place.
        Notes:
            If multiples of a file are specified (such as multiple raw files), only the last found file name will be
            returned
        """
        raw_file = None

        for one_file in source_files:
            if one_file.endswith('_raw'):
                raw_file = one_file

        return raw_file

    @staticmethod
    def get_local_time(timestamp: str) -> str:
        """Returns the time extracted from the timestamp
        Arguments:
            timestamp: the ISO 8601 timestamp string
        Return:
            Returns the extracted time. If a time isn't found, the original string is returned
        """
        if 'T' in timestamp:
            time_only = timestamp.split('T')[1]
            return time_only[0:8]

        return timestamp

    @staticmethod
    def check_raw_file_size(raw_filename: str) -> Optional[str]:
        """Checks if the file may be too large for available memory
        Arguments:
            raw_filename: the path to the RAW file to check
        Return:
            Returns None if size checking passes and an error message if failing
        """
        reserve_memory = 5 * 1024 * 1024    # Megabytes
        # Get the name of the raw file
        raw_file_size = os.stat(raw_filename).st_size

        # Determine the amount of available memory
        available_mem = psutil.virtual_memory().available

        # Determine if we have a fit
        if available_mem <= raw_file_size:
            return "RAW file size %s is too large for available memory %s: '%s'" % \
                   (str(raw_file_size), str(available_mem), raw_filename)
        if available_mem - reserve_memory <= raw_file_size:
            return "RAW file size %s will consume available and reserved memory: %s (%s + %s): '%s'" % \
                   (str(raw_file_size), str(available_mem + reserve_memory), str(available_mem), str(reserve_memory), raw_filename)

        return None

    @staticmethod
    def irradiance_time_extractor(camera_type: str, envlog_file: str) -> tuple:
        """Extract spectral profiles from environment logger json file
        Arguments:
            camera_type: the string representing the camera type
            envlog_file: the path to the environment logger json file
        Return:
            Returns a tuple of the loaded times and spectra
        """
        # For the environmental logger records after 04/26/2016, there would be 24 files per day (1 file per hour, 5 seconds per record)
        # Convert json file to dictionary format file
        with open(envlog_file, "r") as in_file:
            lines = in_file.readlines()
            joined_lines = "".join(lines)
            env_json = json.loads(joined_lines)
            del lines
            del joined_lines

        # assume that time stamp follows in 5 second increments across records since 5 sec/record
        sensor_reading_json = env_json["environment_sensor_readings"]
        num_readings = len(sensor_reading_json)
        if "spectrometers" in sensor_reading_json[0]:
            if camera_type == "swir_new":
                num_bands = len(sensor_reading_json[0]["spectrometers"]["NIRQuest-512"]["spectrum"])
            else:
                num_bands = len(sensor_reading_json[0]["spectrometers"]["FLAME-T"]["spectrum"])
        else:
            num_bands = len(sensor_reading_json[0]["spectrometer"]["spectrum"])

        spectra = np.zeros((num_readings, num_bands))
        times = []
        for idx in range(num_readings):
            # read time stamp
            time_current = sensor_reading_json[idx]["timestamp"]
            array_time = time_current.replace(".", " ").replace("-", " ").replace(":", "").split(" ")
            time_current_r = int(array_time[3])
            times.append(time_current_r)

            # read spectrum from irridiance sensors
            if "spectrometers" in sensor_reading_json[idx]:
                if camera_type == "swir_new":
                    spectrum = sensor_reading_json[0]["spectrometers"]["NIRQuest-512"]["spectrum"]
                else:
                    spectrum = sensor_reading_json[idx]["spectrometers"]["FLAME-T"]["spectrum"]
            else:
                spectrum = sensor_reading_json[idx]["spectrometer"]["spectrum"]

            spectra[idx, :] = spectrum

        return times, spectra

    @staticmethod
    def update_netcdf(input_filename: str, rfl_data, camera_type: str) -> None:
        """Replace rfl_img variable in netcdf with given matrix
        Arguments:
            input_filename: the file to update
            rfl_data: the data to update
            camera_type: the camera type the data is for
        """
        logging.info('Updating %s', input_filename)

        output_filename = input_filename.replace(".nc", "_newrfl.nc")
        logging.debug('Writing data to %s', output_filename)

        with Dataset(input_filename) as src, Dataset(output_filename, "w") as dst:
            # copy global attributes all at once via dictionary
            dst.setncatts(src.__dict__)
            # copy dimensions
            for name, dimension in src.dimensions.items():
                dst.createDimension(name, (len(dimension) if not dimension.isunlimited() else None))

            # copy all file data except for the excluded
            for name, variable in src.variables.items():
                if name == 'Google_Map_View':
                    continue

                # Create variables
                var_dict = src[name].__dict__
                if '_FillValue' in var_dict.keys():
                    dst.createVariable(name, variable.datatype, variable.dimensions, fill_value=var_dict['_FillValue'])
                    del var_dict['_FillValue']
                else:
                    dst.createVariable(name, variable.datatype, variable.dimensions)

                # Set variables to values
                if name != "rfl_img":
                    logging.debug('...%s', name)
                    dst[name][:] = src[name][:]
                else:
                    if camera_type == 'vnir_old':
                        logging.debug('...%s (subset)', name)
                        dst[name][:679, :, :] = rfl_data
                        # 679-955 set to NaN
                        logging.debug('...NaNs')
                        dst[name][679:, :, :] = np.nan

                    elif camera_type == 'vnir_middle':
                        logging.debug('...%s (subset)', name)
                        dst[name][:662, :, :] = rfl_data
                        # 679-955 set to NaN
                        logging.debug('...NaNs')
                        dst[name][662:, :, :] = np.nan
                    else:
                        logging.debug('...%s', name)
                        dst[name][:] = rfl_data

                # copy variable attributes all at once via dictionary
                dst[name].setncatts(var_dict)

            if 'rfl_img' not in src.variables:
                logging.debug('...adding rfl_img')
                dst.createVariable('rfl_img', 'f4')
                dst.variables['rfl_img'] = rfl_data

    @staticmethod
    def get_camera_info(sensor: str, data_date: str) -> tuple:
        """Returns information on a camera based upon the sensor and date
        Arguments:
            sensor: one of 'VNIR' or 'SWIR' (default)
            data_date: date associated with data (in 'YYYY-MM-DD' format)
        Return:
             A tuple of camera type, number of spectral bands, number of irradiance bands, and scanning time. None is
             returned for any value that's missing
        """
        camera_type = None
        num_spectral_bands = None
        num_bands_irradiance = None
        image_scanning_time = None

        if sensor == 'VNIR':
            if data_date < "2018-08-18":
                camera_type = "vnir_old"
                num_spectral_bands = 955
                num_bands_irradiance = 1024
                image_scanning_time = 540
            elif "2018-08-18" <= data_date < "2019-02-26":
                camera_type = "vnir_middle"
                num_spectral_bands = 939
                num_bands_irradiance = 1024
                image_scanning_time = 540
            else:
                camera_type = "vnir_new"
                num_spectral_bands = 939
                num_bands_irradiance = 3648
                # it is observed that it takes an average of 3.5 mins/scan  = 210 seconds
                image_scanning_time = 210
        else:
            if data_date < "2019-02-26":  # Note that no calibration models are available for old&middle swir data
                camera_type = "swir_old_middle"
            else:
                camera_type = "swir_new"
                num_spectral_bands = 275
                num_bands_irradiance = 512
                image_scanning_time = 210

        return camera_type, num_spectral_bands, num_bands_irradiance, image_scanning_time

    @staticmethod
    def apply_calibration(raw_filename: str, sensor: str, data_date: str, timestamp: str, environment_logging: str,
                          out_filename: str) -> None:
        """Applies calibration to the RAW file
        Arguments:
            raw_filename: the path to the raw file
            sensor: the name of the sensor the RAW file represents
            data_date: the date to associate with the data
            timestamp: the timestamp to use for this request
            environment_logging: the environment logging folder to use
            out_filename: the name of the resulting file
        """
        # Disabling warnings to keep algorithm readable
        # pylint: disable=too-many-locals, too-many-statements
        logging.info('Calibrating %s to %s', raw_filename, out_filename)

        # determine type of sensor and age of camera
        camera_type, num_irradiance_bands, image_scanning_time, num_spectral_bands = __internal__.get_camera_info(sensor, data_date)
        logging.info('MODE: ---------- %s ----------', camera_type)
        logging.debug('MODE: irradiance bands: %s', str(num_irradiance_bands))
        logging.debug('MODE: scanning time: %s', str(image_scanning_time))
        logging.debug('MODE: spectral bands: %s', str(num_spectral_bands))

        # load the raw data set
        hdr_filename = raw_filename + '.hdr'
        logging.debug('Loading %s', hdr_filename)
        if not os.path.exists(hdr_filename):
            raise RuntimeError("Missing RAW associated file: '%s'" % hdr_filename)

        raw = envi.open(hdr_filename)
        img_dn = raw.open_memmap()

        # Apply calibration procedure if camera_type == vnir_old, vnir_middle, vnir_new or swir_new.
        # Since no calibration models are available for swir_old and swir_middle, so directly convert old & middle
        # SWIR raw data to netcdf format
        if camera_type == "swir_old_middle":
            # Convert the raw swir_old and swir_middle data to netCDF
            img_dn = np.rollaxis(img_dn, 2, 0)
            __internal__.update_netcdf(out_filename, img_dn, camera_type)

            # free up memory
            del img_dn
            return

        # when camera_type == vnir_old, vnir_middle, vnir_new or swir_new, apply pre-computed calibration models
        # Load the previously created calibration models based on the camera_type
        best_matched = os.path.join(CALIB_ROOT, "calibration_new", camera_type, 'best_matched_index.npy')
        bias_filename = os.path.join(CALIB_ROOT, "calibration_new", camera_type, 'bias_coeff.npy')
        gain_filename = os.path.join(CALIB_ROOT, "calibration_new", camera_type, 'gain_coeff.npy')
        # read EnvLog data
        logging.debug("Reading EnvLog files: %s", environment_logging)
        envlog_tot_time = []
        envlog_spectra = np.array([], dtype=np.int64).reshape(0, image_scanning_time)
        num_file_read = 0
        for one_file in os.listdir(environment_logging):
            if one_file.endswith('environmentlogger.json'):
                logging.debug("Loading environmentlogger file: '%s'", one_file)
                time, spectrum = __internal__.irradiance_time_extractor(camera_type, os.path.join(environment_logging, one_file))
                envlog_tot_time += time
                # print("concatenating %s onto %s" % (spectrum.shape, envlog_spectra.shape))
                envlog_spectra = np.vstack([envlog_spectra, spectrum])
                num_file_read += 1
        logging.info("Read in %s environment logger files", str(num_file_read))

        # Find the best match time range between image time stamp and EnvLog time stamp
        num_irridiance_record = int(image_scanning_time/5)   # 210/5=4.2  ---->  5 seconds per record

        # concatenation of hour, minutes, and seconds of the image time stamp (eg., 12-38-49 to 123849)
        logging.debug("Using timestamp: %s", timestamp)
        image_time = int(__internal__.get_local_time(timestamp).replace(":", ""))
        logging.debug("Image time: %s", str(image_time))

        # compute the absolute difference between
        logging.info('Computing mean spectrum')
        abs_diff_time = np.zeros((len(envlog_tot_time)))
        for k in range(len(envlog_tot_time)):
            abs_diff_time[k] = abs(image_time - envlog_tot_time[k])
        ind_closet_time = np.argmin(abs_diff_time)  # closest time index
        mean_spectrum = np.mean(envlog_spectra[ind_closet_time: ind_closet_time + num_irridiance_record-1, :], axis=0)
        del envlog_spectra
        del abs_diff_time

        # load pre-computed the best matched index between image and irradiance sensor spectral bands
        best_matched_index = np.load(best_matched)
        test_irridance = mean_spectrum[best_matched_index.astype(int).tolist()]
        test_irridance_re = np.resize(test_irridance, (1, num_irradiance_bands))
        del mean_spectrum
        del test_irridance

        # load and apply precomputed coefficient to convert irradiance to DN
        loaded_bias = np.load(bias_filename)
        loaded_gain = np.load(gain_filename)
        if camera_type == "vnir_old":
            test_irridance_re = test_irridance_re[:, 0:679]
            img_dn = img_dn[:, :, 0:679]
        elif camera_type == "vnir_middle":
            test_irridance_re = test_irridance_re[:, 0:662]
            img_dn = img_dn[:, :, 0:662]

        irrad2dn = (loaded_gain * test_irridance_re) + loaded_bias
        del loaded_gain
        del test_irridance_re
        del loaded_bias

        # reflectance computation
        logging.info("Computing reflectance")
        rfl_data = img_dn/irrad2dn
        rfl_data = np.rollaxis(rfl_data, 2, 0)

        # free up memory
        del img_dn
        del irrad2dn

        # save as ENVI file (RGB bands: 392, 252, 127)
        #out_file = os.path.join('ref_%s.hdr' % raw_file)
        #envi.save_image(out_file, Ref, dtype=np.float32, interleave='bil', force = 'True', metadata=head_file)

        # Save Ref as a .npy file
        #out_file = os.path.join(out_path, 'ref_%s.npy' % raw_file)
        #np.save(out_file, rfl_data)

        # Write to nc file
        logging.debug("About to save netcdf file: %s", out_filename)
        __internal__.update_netcdf(out_filename, rfl_data, camera_type)

        # free up memory
        del rfl_data


def add_parameters(parser: argparse.ArgumentParser) -> None:
    """Adds parameters
    Arguments:
        parser: instance of argparse.ArgumentParser
    """
    parser.add_argument("--date_override", help="override default date by specifying a new one in ISO 8601 format")
    parser.add_argument('--skip_memory_check', action="store_true", help='do not perform memory check when processing RAW file')
    parser.add_argument('--environment_logger', help='the path to the EnvironmentLogger folder')
    parser.add_argument('sensor', choices=['VNIR', 'SWIR'], help='the name of the sensor associated with the source files')


def perform_process(transformer: transformer_class.Transformer, check_md: dict, transformer_md: list, full_md: list) -> dict:
    """Performs the processing of the data
    Arguments:
        transformer: instance of transformer class
        check_md: request specific metadata
        transformer_md: metadata associated with previous runs of the transformer
        full_md: the full set of metadata available to the transformer
    Return:
        Returns a dictionary with the results of processing
    """
    # pylint: disable=unused-argument
    (raw_filename) = __internal__.get_needed_files(check_md['list_files']())
    if not raw_filename:
        return {'code': -1000, 'error': "A RAW file was not found in the provided list"}
    if not os.path.isdir(transformer.args.environment_logger):
        return {'code': -1001, 'error': "The environmental logger folder was not found: '%s'" % transformer.args.environment_logger}
    if not transformer.args.skip_memory_check:
        error_msg = __internal__.check_raw_file_size(raw_filename)
        if error_msg:
            return {'code': -1002, 'error': "Try using the --skip_memory_check switch. " + error_msg}

    # Get the destination file names
    out_base_filename = os.path.join(check_md['working_folder'], os.path.splitext(os.path.basename(raw_filename))[0])
    out_filename = out_base_filename + '.nc'
    xps_filename = out_base_filename + '_xps.nc'
    calibration_filename = out_base_filename + '_newrfl.nc'
    logging.debug("Output filename: %s", out_filename)
    logging.debug("XPS filename: %s", xps_filename)
    logging.debug("Calibration filename: %s", calibration_filename)
    del out_base_filename

    # Run the commands to create the files
    logging.info('Running the hyperspectral workflow')
    logging.debug("Calling hyperspectal_workflow.sh")
    subprocess_code = subprocess.call(["bash", "hyperspectral_workflow.sh", "-d", "1",
                                       "--output_xps_img", xps_filename, "-i", raw_filename, "-o", out_filename])
    logging.debug("Subprocess return code: %s", str(subprocess_code))

    logging.info("Running calibration")
    data_date = transformer.args.date_override if transformer.args.date_override else check_md['timestamp'][:10]
    data_date = data_date.replace('/', '-').replace('_', '-')
    logging.debug("Sensor: %s  Data date: %s", transformer.args.sensor, data_date)
    try:
        __internal__.apply_calibration(raw_filename, transformer.args.sensor, data_date, check_md['timestamp'],
                                       transformer.args.environment_logger, out_filename)
    except Exception as ex:
        msg = "Exception caught while applying calibration: " + str(ex)
        logging.exception(msg)
        return {'code': -1004, 'error': msg}

    return {'code': 0
            }
