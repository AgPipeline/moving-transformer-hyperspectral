# Version 1.0 template-transformer-simple 

FROM agpipeline/gantry-base-image:1.3
LABEL maintainer="Chris Schnaufer <schnaufer@email.arizona.edu>"

COPY requirements.txt packages.txt /home/extractor/

USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN [ -s /home/extractor/packages.txt ] && \
    (echo 'Installing packages' && \
        apt-get update && \
        cat /home/extractor/packages.txt | xargs apt-get install -y --no-install-recommends && \
        rm /home/extractor/packages.txt && \
        apt-get autoremove -y && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*) || \
    (echo 'No packages to install' && \
        rm /home/extractor/packages.txt)

RUN [ -s /home/extractor/requirements.txt ] && \
    (echo "Install python modules" && \
    python3 -m pip install -U --no-cache-dir pip && \
    python3 -m pip install --no-cache-dir setuptools && \
    python3 -m pip install --no-cache-dir -r /home/extractor/requirements.txt && \
    rm /home/extractor/requirements.txt) || \
    (echo "No python modules to install" && \
    rm /home/extractor/requirements.txt)

USER extractor

#RUN cd ~ \
#    && curl https://repo.continuum.io/archive/Anaconda3-2019.03-Linux-x86_64.sh > Anaconda3-2019.03-Linux-x86_64.sh \
#    && bash Anaconda3-2019.03-Linux-x86_64.sh -b
#
##install conda-forge packages
#RUN ~/anaconda3/bin/conda config --add channels conda-forge \
#    && ~/anaconda3/bin/conda config --set allow_conda_downgrades true
#
#RUN ~/anaconda3/bin/conda install -y \
#         libnetcdf \
#         hdf5 \
#         netcdf4 \
#         nco \
#         "gdal>2.2.4" \
#         libiconv \
#         xerces-c \
#         geos \
#         udunits2

COPY *.py *.nc *.nco *.sh /home/extractor/
COPY calibration /home/extractor/calibration
COPY calibration_939 /home/extractor/calibration_939
COPY calibration_new /home/extractor/calibration_new

ENV PATH="/home/extractor:${PATH}"
