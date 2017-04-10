### for CMU rocks cluster ###
#PBS -j oe
#PBS -k oe
#PBS -o log
#PBS -d .
#PBS -V
#PBS -l walltime=48:00:00
#PBS -N DQN 
#PBS -q gpu

module load gcc-4.9.2
module load cuda-8.0
export CUDA_VISIBLE_DEVICES=`qstat -n $PBS_JOBID|awk 'END {split ($NF, a, "/"); printf ("%s\n", a[2])}'`
source activate p_3

echo $HOSTNAME
echo "Running on gpu"
echo "Device = $CUDA_VISIBLE_DEVICES"

# run the experiment script
python dqn_atari.py --env=Breakout-v0
