# Hyperspectral extractors
Converts hyperspectral to netCDF and applies calibration

## Authors

- Chris Schnaufer, University of Arizona, Tucson, AZ
- Max Burnette, National Supercomputing Applications, Urbana, Il

## Extractor Description 

This repository contains extractors that process data originating from:
- Hyperspec INSPECTOR SWIR camera
- Hyperspec INSPECTOR VNIR camera

## Theoretical basis 

The hyperspectral calibration procedure is documented at https://github.com/terraref/computing-pipeline/issues/282.
The implementation is undergoing improvement (e.g., better target calibrations, more reliable factory calibrations, improved interpolation methods) as experience is gained.

Also read about the [limitations](#limitations) of the implementation.

## Sample Docker Command Line
Note that processing hyperspectral data can consume a large amount of memory and disk space.
We recommend 64GiB of memory and at least 30GiB of available disk space.

Below is a sample command line that shows how the hyperspectral Docker image could be run.
An explanation of the command line options used follows.
Be sure to read up on the [docker run](https://docs.docker.com/engine/reference/run/) command line for more information.

The data used in this example can be found on [Google Drive](https://drive.google.com/open?id=1-sOpUrBqLxZDCqvBLa8KJ4WjPkDdSb-5) as a compressed tar file.

```docker run --rm --mount "source=/home/test,target=/mnt,type=bind" -e "BETYDB_URL=<BETYdb URL>" -e "BETYDB_KEY=<BETYdb Key>" agpipeline/hyperspectral:3.0 --metadata /mnt/f46c9e11-de52-40ca-8258-c64427f877f0_metadata_cleaned.json --working_space /mnt --date_override "2019-03-31" --environment_logger /mnt/2019-03-31 VNIR /mnt/f46c9e11-de52-40ca-8258-c64427f877f0_raw```

This example command line assumes the source files are located in the `/home/test` folder of the local machine.
The name of the image to run is `agpipeline/hyperspectral:3.0`.

We are using the same folder for the source files and the output files.
By using multiple `--mount` options, the source and output files can be separated.

**Docker commands** \
Everything between 'docker' and the name of the image are docker commands.

- `run` indicates we want to run an image
- `--rm` automatically delete the image instance after it's run
- `--mount "src=/home/test,target=/mnt,type=bind"` mounts the `/home/test` folder to the `/mnt` folder of the running image
- `-e "BETYDB_URL=<BETYdb URL>"` specifies the URL of the BETYdb instance to fetch plot geometries from
- `-e "BETYDB_KEY=<BETYdb Key>"` specifies the permission key used to access the BETYdb instance

We mount the `/home/test` folder to the running image to make files available to the software in the image.

**Image's commands** \
The command line parameters after the image name are passed to the software inside the image.
Note that the paths provided are relative to the running image (see the --mount option specified above).

- `--working_space "/mnt"` specifies the folder to use as a workspace
- `--metadata "/mnt/f46c9e11-de52-40ca-8258-c64427f877f0_metadata_cleaned.json"` is the name of the cleaned metadata
- `--date_override "2019-03-31"` optional override for the capture date used to inform the algorithm on sensor properties
- `--environment_logger /mnt/2019-03-31` the folder containing EnvironmentLogger files
- `VNIR` specifies that we're processing VNIR files
- `/mnt/f46c9e11-de52-40ca-8258-c64427f877f0_raw` the RAW file to be processed 

## Technical Information
This section provides technical information regarding the implementation of the algorithm.

### Inputs and Outputs 

This extractor processes ENVI BIL (band-interleaved-by-line) files into netCDF. 

_Input_

  - Checks whether the file is a _raw file (file name ends with '_raw')
  
_Output_

  - A .nc netCDF file corresponding to the _raw file

#### Limitations<a name="limitations" /> 

1. Only valid for 300-800nm (range of downwelling radiometer)
2. Raw hyperspectral exposures are calibrated for images in full sunlight. Other times and cloudy days are not well-tested yet. 
3. Zenith angles used in the calibration data are: 42.3, 47.6, 53.0, 58.4, 64.0, 75.1, 80.7, 86.5
   * The closer the raw data is to these angles the better the result  
4. The calibration needs improvement to obtain accurate absolute reflectances. Environmental conditions (such as shade and specular reflection) and irregular calibration of known targets (such as tilted surfaces and field-based calibration) can bias retrieved reflectances by an unknown factor. However, the scale bias factors out of indices created as ratios of reflectances, e.g., (A-B) / (A+B).

### Application 

#### Files:

1. hyperspectral_workflow.sh

This is the main shell script:

- -c dfl_lvl  Compression level [0..9] (empty means none) (default )
- -d dbg_lvl  Debugging level (default 0)
- -h          Create indices file. This has the same root name as out_fl but with the suffix "_ind.nc"    
- -I drc_in   Input directory (empty means none) (default )
- -i in_fl    Input filename (required) (default )
- -j job_nbr  Job simultaneity for parallelism (default 6)
- -m msk_fl   location of Netcdf Soil Mask (Level 1 data) applied when creating indices file
- -n nco_opt  NCO options (empty means none) (default )
- -N ntl_out  Interleave-type of output (default bsq)
- -O drc_out  Output directory (default /home/butowskh/terraref/extractors-hyperspectral/hyperspectral)
- -o out_fl   Output-file (empty derives from Input filename) (default )
- -p par_typ  Parallelism type (default bck)
- -t typ_out  Type of netCDF output (default NC_USHORT)
- -T drc_tmp  Temporary directory (default /gpfs_scratch/arpae/imaging_spectrometer)
- -u unq_sfx  Unique suffix (prevents intermediate files from sharing names) (default .pid140080)
- -x xpt_flg  Experimental (default No)


2. CalculationWorks.py

A supporting module for EnvironmentalLoggerAnalyser.py and JsonDealer.py.
This module is in charge of all the calculation works needed in the
EnvironmentalLoggerAnalyser.py (converting the data made by environmental logger)
and JsonDealer.py (group up the supporting files for data_raw).

* EnvironmentalLoggerAnalyzer.py

This module will read data generated by Environmental Sensor and convert to netCDF file

* JsonDealer.py

This module parses JSON formatted metadata and data and header provided by LemnaTec and outputs a formatted netCDF4 file

* DataProcess.py

This module will process the data file and export a netCDF with variables 
from it and dimesions (band, x, y) from its hdr file

* hyperspectral_calibration.nco

NCO/ncap2 script to process and calibrate TERRAREF exposure data

### Failure Conditions

### Related GitHub issues and documentation

1. [Notes from meeting on calibration options](https://docs.google.com/document/d/e/2PACX-1vRKArTMn0aU90KoFKe-HCYMuFubcW_WLUZsFCWCT2rENhitzf00tLktYm6EG2DIB3X5rSRD1A1DOZhL/pub)
2. First (alpha) calibration proceedure https://github.com/terraref/computing-pipeline/issues/88
3. Second (radiometer based) calibration 
   * List of tasks https://github.com/terraref/computing-pipeline/issues/281 
   * Algorithm documentation https://github.com/terraref/computing-pipeline/issues/282