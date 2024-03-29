#!/usr/bin/env python
"""Run Atari Environment with DQN."""
import argparse
import os
from deeprl_hw2.dqn import DQNAgent
from deeprl_hw2.utils import RLEEnvPerLifeWrapper
from rle import rle
import gym
from gym import wrappers
import pickle

def get_output_folder(parent_dir, env_name):
    """Return save folder.

    Assumes folders in the parent_dir have suffix -run{run
    number}. Finds the highest run number and sets the output folder
    to that number + 1. This is just convenient so that if you run the
    same script multiple times tensorboard can plot all of the results
    on the same plots with different names.

    Parameters
    ----------
    parent_dir: str
      Path of the directory containing all experiment runs.

    Returns
    -------
    parent_dir/run_dir
      Path to this run's save directory.
    """
    os.makedirs(parent_dir, exist_ok=True)
    experiment_id = 0
    for folder_name in os.listdir(parent_dir):
        if not os.path.isdir(os.path.join(parent_dir, folder_name)):
            continue
        try:
            folder_name = int(folder_name.split('-run')[-1])
            if folder_name > experiment_id:
                experiment_id = folder_name
        except:
            pass
    experiment_id += 1

    parent_dir = os.path.join(parent_dir, env_name)
    parent_dir = parent_dir + '-run{}'.format(experiment_id)
    os.mkdir(parent_dir)
    return parent_dir


def trace2mem(args):
    from deeprl_hw2.preprocessors import AtariPreprocessor
    from deeprl_hw2.core import ReplayMemory
    import glob
    import pickle
    
    memory = ReplayMemory(args)
    atari_processor = AtariPreprocessor()

    count = 0

    for trace_path in glob.glob("%s/*.dmp" % args.trace_dir):
        with open(trace_path, 'rb') as tdump:
            trace = pickle.load(tdump)
        for state, action, reward, done in zip(trace["state"], trace["action"], trace["reward"], trace["done"]):
            processed_state = atari_processor.process_state_for_memory(state)
            processed_reward = atari_processor.process_reward(reward)
            memory.append(processed_state, action, processed_reward, done)
            count += 1
        if len(trace["state"]) > len(trace["reward"]):
            processed_state = atari_processor.process_state_for_memory(trace["state"][-1])
            memory.append(processed_state, trace["action"][-1], 0, trace["done"][-1])
            count += 1

    with open(args.mem_dump, 'wb') as mdump:
        print(count)
        pickle.dump(memory, mdump)


def main():  # noqa: D103
    parser = argparse.ArgumentParser(description='Run DQN on Atari Breakout')
    parser.add_argument('--env', default='Breakout-v0', help='Atari env name')
    parser.add_argument('-o', '--output', default='../log/', help='Directory to save data to')
    parser.add_argument('--seed', default=0, type=int, help='Random seed')
    parser.add_argument('--gamma', default=0.99, type=float, help='Discount factor')
    parser.add_argument('--batch_size', default=32, type=int, help='Minibatch size')
    parser.add_argument('--learning_rate', default=0.0001, type=float, help='Learning rate')
    parser.add_argument('--initial_epsilon', default=1.0, type=float, help='Initial exploration probability in epsilon-greedy')
    parser.add_argument('--final_epsilon', default=0.05, type=float, help='Final exploration probability in epsilon-greedy')
    parser.add_argument('--exploration_steps', default=2000000, type=int, help='Number of steps over which the initial value of epsilon is linearly annealed to its final value')
    parser.add_argument('--num_samples', default=10000000, type=int, help='Number of training samples from the environment in training')
    parser.add_argument('--num_frames', default=4, type=int, help='Number of frames to feed to Q-Network')
    parser.add_argument('--num_frames_mv', default=10, type=int, help='Number of frames to used to detect movement')
    parser.add_argument('--frame_width', default=84, type=int, help='Resized frame width')
    parser.add_argument('--frame_height', default=84, type=int, help='Resized frame height')
    parser.add_argument('--replay_memory_size', default=1000000, type=int, help='Number of replay memory the agent uses for training')
    parser.add_argument('--target_update_freq', default=10000, type=int, help='The frequency with which the target network is updated')
    parser.add_argument('--train_freq', default=4, type=int, help='The frequency of actions wrt Q-network update')
    parser.add_argument('--save_freq', default=200000, type=int, help='The frequency with which the network is saved')
    parser.add_argument('--eval_freq', default=200000, type=int, help='The frequency with which the policy is evlauted')    
    parser.add_argument('--num_burn_in', default=50000, type=int, help='Number of steps to populate the replay memory before training starts')
    parser.add_argument('--load_network', default=False, action='store_true', help='Load trained mode')
    parser.add_argument('--load_network_path', default='', help='the path to the trained mode file')
    parser.add_argument('--net_mode', default='dqn', help='choose the mode of net, can be linear, dqn, duel')
    parser.add_argument('--max_episode_length', default = 10000, type=int, help = 'max length of each episode')
    parser.add_argument('--num_episodes_at_test', default = 10, type=int, help='Number of episodes the agent plays at test')
    parser.add_argument('--ddqn', default=False, dest='ddqn', action='store_true', help='enable ddqn')
    parser.add_argument('--train', default=True, dest='train', action='store_true', help='Train mode')
    parser.add_argument('--test', dest='train', action='store_false', help='Test mode')
    parser.add_argument('--no_experience', default=False, action='store_true', help='do not use experience replay')
    parser.add_argument('--no_target', default=False, action='store_true', help='do not use target fixing')
    parser.add_argument('--no_monitor', default=False, action='store_true', help='do not record video')
    parser.add_argument('-p', '--platform', default='rle', help='rle or atari. rle: rle; atari: gym-atari')
    parser.add_argument('-pl', '--perlife', default=False, action='store_true', help='use per life or not. ')
    parser.add_argument('-mv', '--mv_reward', default=False, action='store_true', help='use movement reward or not')
    parser.add_argument('-c', '--clip_reward', default=False, action='store_true', help='clip reward or not')
    parser.add_argument('--decay_reward', default=False, action='store_true', help='decay reward or not')
    parser.add_argument('--expert_memory', default=None, help='path of the expert memory')
    parser.add_argument('--initial_prob_replaying_expert', default=1.0, type=float, help='Initial probability of using expert replaying memory')
    parser.add_argument('--final_prob_replaying_expert', default=0.05, type=float, help='Final probability of using expert replaying memory')
    parser.add_argument('--steps_replaying_expert', default=1000000, type=float, help='# steps over which the initial prob of replaying expert memory is linearly annealed to its final value') 
    parser.add_argument('--trace_dir', default='', help='the trace dir for expert')
    parser.add_argument('--trace2mem', default=False, action='store_true', help='convert trace to memory')
    parser.add_argument('--mem_dump', default='', help='the path of memory dump')
    args = parser.parse_args()
    args.output = get_output_folder(args.output, args.env)

    if args.trace2mem:
        trace2mem(args)
        exit(0)

    if args.platform == 'atari':
        env = gym.make(args.env)
    else:
        rom_path = 'roms/' + args.env 
        if args.no_monitor:
            env = rle(rom_path, record=True, path=args.output)
        else:
            env = rle(rom_path)
    print("Output saved to: ", args.output)
    print("Args used:")
    print(args)

    # here is where you should start up a session,
    # create your DQN agent, create your model, etc.
    # then you can run your fit method.

    num_actions = env.action_space.n
    print("Game ", args.env, " #actions: ", num_actions)
    dqn = DQNAgent(args, num_actions)
    if args.train:
        print("Training mode.")
        if args.perlife:
            env = RLEEnvPerLifeWrapper(env)
        dqn.fit(env, args.num_samples, args.max_episode_length)
    else:
        print("Evaluation mode.")
        dqn.evaluate(env, args.num_episodes_at_test, args.max_episode_length, not args.no_monitor)

if __name__ == '__main__':
    main()
