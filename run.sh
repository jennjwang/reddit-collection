#!/bin/bash

# Default resources are 1 core with 2.8GB of memory per core.

# job name:
#SBATCH -J Reddit_Parse


# email error reports
#SBATCH --mail-type=ALL

# output file
#SBATCH -J parsing
#SBATCH -o parsing-%j.out
#SBATCH -e parsing-%j.err
# %A is the job id (as you find it when searching for your running / finished jobs on the cluster)
# %a is the array id of your current array job


# Request runtime, memory, cores
#SBATCH --time=48:00:00
#SBATCH --mem=60G
#SBATCH -c 8
#SBATCH -N 1

# machine='ccv'

source ~/cs4sc/bin/activate
python3 model.py
deactivate