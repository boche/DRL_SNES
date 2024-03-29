from deeprl_hw2.policy import *
from deeprl_hw2.objectives import *
from deeprl_hw2.preprocessors import *
from deeprl_hw2.utils import *
from deeprl_hw2.core import *
from keras.optimizers import (Adam, RMSprop)
import tensorflow as tf
import numpy as np
import pdb
import keras
from keras.layers import (Activation, Convolution2D, Dense, Flatten, Input,
        Permute, merge, Lambda)
from keras.models import Model
from keras import backend as K
import sys
from gym import wrappers
import pickle

config = tf.ConfigProto()
config.gpu_options.allow_growth=True
sess = tf.Session(config=config)
K.set_session(sess)
K.get_session().run(tf.initialize_all_variables())

"""Main DQN agent."""

def create_model(input_shape, num_actions, mode, model_name='q_network'):  # noqa: D103
    """Create the Q-network model.

    Use Keras to construct a keras.models.Model instance (you can also
    use the SequentialModel class).

    We highly recommend that you use tf.name_scope as discussed in
    class when creating the model and the layers. This will make it
    far easier to understnad your network architecture if you are
    logging with tensorboard.

    Parameters
    ----------
    window: int
      Each input to the network is a sequence of frames. This value
      defines how many frames are in the sequence.
    input_shape: tuple(int, int, int), rows, cols, channels
      The expected input image size.
    num_actions: int
      Number of possible actions. Defined by the gym environment.
    model_name: str
      Useful when debugging. Makes the model show up nicer in tensorboard.

    Returns
    -------
    keras.models.Model
      The Q-model.
    """
    assert(mode in ("linear", "duel", "dqn"))
    with tf.variable_scope(model_name):
        input_data = Input(shape = input_shape, name = "input")
        if mode == "linear":
            flatten_hidden = Flatten(name = "flatten")(input_data)
            output = Dense(num_actions, name = "output")(flatten_hidden)
        else:
            h1 = Convolution2D(32, (8, 8), strides = 4, activation = "relu", name = "conv1")(input_data)
            h2 = Convolution2D(64, (4, 4), strides = 2, activation = "relu", name = "conv2")(h1)
            h3 = Convolution2D(64, (3, 3), strides = 1, activation = "relu", name = "conv3")(h2)
            flatten_hidden = Flatten(name = "flatten")(h3)
            if mode == "dqn":
                h4 = Dense(512, activation='relu', name = "fc")(flatten_hidden)
                output = Dense(num_actions, name = "output")(h4)
            elif mode == "duel":
                value_hidden = Dense(512, activation = 'relu', name = 'value_fc')(flatten_hidden)
                value = Dense(1, name = "value")(value_hidden)
                action_hidden = Dense(512, activation = 'relu', name = 'action_fc')(flatten_hidden)
                action = Dense(num_actions, name = "action")(action_hidden)
                action_mean = Lambda(lambda x: tf.reduce_mean(x, axis = 1, keep_dims = True), name = 'action_mean')(action) 
                output = Lambda(lambda x: x[0] + x[1] - x[2], name = 'output')([action, value, action_mean])
    return Model(inputs = input_data, outputs = output)

def save_scalar(step, name, value, writer):
    """Save a scalar value to tensorboard.
      Parameters
      ----------
      step: int
        Training step (sets the position on x-axis of tensorboard graph.
      name: str
        Name of variable. Will be the name of the graph in tensorboard.
      value: float
        The value of the variable at this step.
      writer: tf.FileWriter
        The tensorboard FileWriter instance.
      """
    summary = tf.Summary()
    summary_value = summary.value.add()
    summary_value.simple_value = float(value)
    summary_value.tag = name
    writer.add_summary(summary, step)

class DQNAgent:
    """Class implementing DQN.

    This is a basic outline of the functions/parameters you will need
    in order to implement the DQNAgnet. This is just to get you
    started. You may need to tweak the parameters, add new ones, etc.

    Feel free to change the functions and funciton parameters that the class 
    provides.

    We have provided docstrings to go along with our suggested API.

    Parameters
    ----------
    q_network: keras.models.Model
      Your Q-network model.
    preprocessor: deeprl_hw2.core.Preprocessor
      The preprocessor class. See the associated classes for more
      details.
    memory: deeprl_hw2.core.Memory
      Your replay memory.
    gamma: float
      Discount factor.
    target_update_freq: float
      Frequency to update the target network. You can either provide a
      number representing a soft target update (see utils.py) or a
      hard target update (see utils.py and Atari paper.)
    num_burn_in: int
      Before you begin updating the Q-network your replay memory has
      to be filled up with some number of samples. This number says
      how many.
    train_freq: int
      How often you actually update your Q-Network. Sometimes
      stability is improved if you collect a couple samples for your
      replay memory, for every Q-network update that you run.
    batch_size: int
      How many samples in each minibatch.
    """
    def __init__(self, args, num_actions):
        self.num_actions = num_actions
        input_shape = (args.frame_height, args.frame_width, args.num_frames)
        self.history_length = max(args.num_frames, args.num_frames_mv) - 1
        self.history_processor = HistoryPreprocessor(self.history_length)
        self.atari_processor = AtariPreprocessor()
        self.memory = ReplayMemory(args)
        self.policy = LinearDecayGreedyEpsilonPolicy(args.initial_epsilon, args.final_epsilon, args.exploration_steps)
        self.decay_reward = args.decay_reward
        self.initial_epsilon = args.initial_epsilon
        self.final_epsilon = args.final_epsilon
        self.exploration_steps = args.exploration_steps
        self.gamma = args.gamma
        self.target_update_freq = args.target_update_freq
        self.num_burn_in = args.num_burn_in
        self.train_freq = args.train_freq
        self.batch_size = args.batch_size
        self.learning_rate = args.learning_rate
        self.frame_width = args.frame_width
        self.frame_height = args.frame_height
        self.num_frames = args.num_frames
        self.num_frames_mv = args.num_frames_mv
        self.output_path = args.output
        self.save_freq = args.save_freq
        self.load_network = args.load_network
        self.load_network_path = args.load_network_path
        self.enable_ddqn = args.ddqn
        self.net_mode = args.net_mode
        self.q_network = create_model(input_shape, num_actions, self.net_mode, "QNet")
        self.target_network = create_model(input_shape, num_actions, self.net_mode, "TargetNet")
        print("Net mode: %s, Using double dqn: %s" % (self.net_mode, self.enable_ddqn))
        self.eval_freq = args.eval_freq
        self.no_experience = args.no_experience
        self.no_target = args.no_target
        self.mv_reward = args.mv_reward
        self.clip_reward = args.clip_reward
        self.expert_memory = None
        if args.expert_memory != None:
            with open(args.expert_memory, 'rb') as mdump:
                self.expert_memory = pickle.load(mdump)
        self.expert_prob = args.initial_prob_replaying_expert
        self.final_prob_replaying_expert = args.final_prob_replaying_expert
        self.decay_step_replaying_expert = (self.final_prob_replaying_expert- args.initial_prob_replaying_expert)/args.steps_replaying_expert
        print("Target fixing: %s, Experience replay: %s" % (not self.no_target, not self.no_experience))

        # initialize target network
        self.target_network.set_weights(self.q_network.get_weights())
        self.final_model = None
        self.compile()

    def compile(self, optimizer = None, loss_func = None):
        """Setup all of the TF graph variables/ops.

        This is inspired by the compile method on the
        keras.models.Model class.

        This is a good place to create the target network, setup your
        loss function and any placeholders you might need.
        
        You should use the mean_huber_loss function as your
        loss_function. You can also experiment with MSE and other
        losses.

        The optimizer can be whatever class you want. We used the
        keras.optimizers.Optimizer class. Specifically the Adam
        optimizer.
        """
        if loss_func is None:
            loss_func = mean_huber_loss
            # loss_func = 'mse'
        if optimizer is None:
            optimizer = Adam(lr = self.learning_rate)
            # optimizer = RMSprop(lr=0.00025)
        with tf.variable_scope("Loss"):
            state = Input(shape = (self.frame_height, self.frame_width, self.num_frames) , name = "states")
            action_mask = Input(shape = (self.num_actions,), name = "actions")
            qa_value = self.q_network(state)
            qa_value = merge([qa_value, action_mask], mode = 'mul', name = "multiply")
            qa_value = Lambda(lambda x: tf.reduce_sum(x, axis=1, keep_dims = True), name = "sum")(qa_value)

        self.final_model = Model(inputs = [state, action_mask], outputs = qa_value)
        self.final_model.compile(loss=loss_func, optimizer=optimizer)

    def calc_q_values(self, state):
        """Given a state (or batch of states) calculate the Q-values.

        Basically run your network on these states.

        Return
        ------
        Q-values for the state(s)
        """
        state = state[None, :, :, :]
        return self.q_network.predict_on_batch(state)

    def select_action(self, state, is_training = True, **kwargs):
        """Select the action based on the current state.

        You will probably want to vary your behavior here based on
        which stage of training your in. For example, if you're still
        collecting random samples you might want to use a
        UniformRandomPolicy.

        If you're testing, you might want to use a GreedyEpsilonPolicy
        with a low epsilon.

        If you're training, you might want to use the
        LinearDecayGreedyEpsilonPolicy.

        This would also be a good place to call
        process_state_for_network in your preprocessor.

        Returns
        --------
        selected action
        """
        q_values = self.calc_q_values(state)
        if is_training:
            if kwargs['policy_type'] == 'UniformRandomPolicy':
                return UniformRandomPolicy(self.num_actions).select_action()
            else:
                # linear decay greedy epsilon policy
                return self.policy.select_action(q_values, is_training)
        else:
            return GreedyEpsilonPolicy(0.05).select_action(q_values)

    def update_policy(self, current_sample):
        """Update your policy.

        Behavior may differ based on what stage of training your
        in. If you're in training mode then you should check if you
        should update your network parameters based on the current
        step and the value you set for train_freq.

        Inside, you'll want to sample a minibatch, calculate the
        target values, update your network, and then update your
        target values.

        You might want to return the loss and other metrics as an
        output. They can help you monitor how training is going.
        """
        batch_size = self.batch_size

        if self.no_experience:
            states = np.stack([current_sample.state])
            next_states = np.stack([current_sample.next_state])
            rewards = np.asarray([current_sample.reward])
            mask = np.asarray([1 - int(current_sample.is_terminal)])

            action_mask = np.zeros((1, self.num_actions))
            action_mask[0, current_sample.action] = 1.0
        else:
            if self.expert_memory != None:
                expert_samples_num = int(round(batch_size * self.expert_prob)) 
                learner_samples_num = batch_size - expert_samples_num
                self.expert_prob = max(self.expert_prob+self.decay_step_replaying_expert, self.final_prob_replaying_expert)
                samples = self.memory.sample(learner_samples_num) + self.expert_memory.sample(expert_samples_num)
            else:
                samples = self.memory.sample(batch_size)
            samples = self.atari_processor.process_batch(samples)

            states = np.stack([x.state for x in samples])
            actions = np.asarray([x.action for x in samples])
            action_mask = np.zeros((batch_size, self.num_actions))
            action_mask[range(batch_size), actions] = 1.0

            next_states = np.stack([x.next_state for x in samples])
            mask = np.asarray([1 - int(x.is_terminal) for x in samples])
            rewards = np.asarray([x.reward for x in samples])

        if self.no_target:
            next_qa_value = self.q_network.predict_on_batch(next_states)
        else:
            next_qa_value = self.target_network.predict_on_batch(next_states)

        if self.enable_ddqn:
            qa_value = self.q_network.predict_on_batch(next_states)
            max_actions = np.argmax(qa_value, axis = 1)
            next_qa_value = next_qa_value[range(batch_size), max_actions]
        else:
            next_qa_value = np.max(next_qa_value, axis = 1)
        target = rewards + self.gamma * mask * next_qa_value

        return self.final_model.train_on_batch([states, action_mask], target), np.mean(target)

    def fit(self, env, num_iterations, max_episode_length=None):
        """Fit your model to the provided environment.

        Its a good idea to print out things like loss, average reward,
        Q-values, etc to see if your agent is actually improving.

        You should probably also periodically save your network
        weights and any other useful info.

        This is where you should sample actions from your network,
        collect experience samples and add them to your replay memory,
        and update your network parameters.

        Parameters
        ----------
        env: gym.Env
          This is your Atari environment. You should wrap the
          environment using the wrap_atari_env function in the
          utils.py
        num_iterations: int
          How many samples/updates to perform.
        max_episode_length: int
          How long a single episode should last before the agent
          resets. Can help exploration.
        """
        is_training = True
        sess = tf.get_default_session()
        writer = tf.summary.FileWriter(self.output_path, sess)
        writer.add_graph(tf.get_default_graph())
        print("Training starts.")
        self.save_model(0)

        state = env.reset()
        burn_in = True
        idx_episode = 1
        episode_loss = .0
        episode_frames = 0
        episode_reward = .0
        episode_raw_reward = .0
        episode_no_explore_reward = .0
        episode_target_value = .0
        burn_in_mv_rewards = []
        mv_threshold = -1
        burn_in_raw_reward = []
        burn_in_min_raw_reward = 99999
        mv_reward = 0
        explore_step = (self.final_epsilon - self.initial_epsilon) / self.exploration_steps
        for t in range(self.num_burn_in + num_iterations):
            history = self.history_processor.process_state_for_network(
                self.atari_processor.process_state_for_network(state))
            action_state = history[:, :, -self.num_frames:]
            mv_history = history[:, :, -self.num_frames_mv:]
            policy_type = "UniformRandomPolicy" if burn_in else "LinearDecayGreedyEpsilonPolicy"
            action = self.select_action(action_state, is_training, policy_type = policy_type)
            processed_state = self.atari_processor.process_state_for_memory(state)

            state, reward, done, info = env.step(action)
            no_explore_reward = reward
            
            processed_next_state = self.atari_processor.process_state_for_network(state)
            if burn_in and reward > 0:
                burn_in_min_raw_reward = min(burn_in_min_raw_reward, reward)
            if self.mv_reward:
                if burn_in:
                    burn_in_mv_rewards.append(np.mean(abs(mv_history-processed_next_state[:,:,np.newaxis]), axis=(0,1)))
                    #burn_in_raw_reward.append(reward)
                else:
                    if mv_threshold == -1:
                        sorted_mv_reward_min=sorted(np.array(burn_in_mv_rewards).min(axis=1))
                        mv_threshold = sorted_mv_reward_min[-int(len(sorted_mv_reward_min)/self.num_actions)]
                    diff = np.mean(abs(mv_history-processed_next_state[:,:,np.newaxis]), axis=(0,1))
                    mv_reward = 0.9 * (min(diff) > mv_threshold)
                    #min_raw_reward = min([x for x in burn_in_raw_reward if x != 0])
                    #pdb.set_trace()

            action_next_state = np.dstack((action_state, processed_next_state))
            action_next_state = action_next_state[:, :, 1:]
            
            if self.decay_reward:
                prob = self.initial_epsilon + min(t, self.exploration_steps) * explore_step
            else:
                prob = 1.0
            with_explore_reward = 2 * reward / float(burn_in_min_raw_reward)
            #with_explore_reward = reward
            if np.random.rand() < prob:
                with_explore_reward += mv_reward
            if self.clip_reward:
                processed_reward = self.atari_processor.process_reward(with_explore_reward)
            else:
                processed_reward = with_explore_reward
            # if self.clip_reward:
                # processed_reward = self.atari_processor.process_reward(reward+mv_reward)
            # else:
                # processed_reward = 2*reward/float(burn_in_min_raw_reward) + mv_reward

            self.memory.append(processed_state, action, processed_reward, done)
            current_sample = Sample(action_state, action, processed_reward, action_next_state, done)
            
            if not burn_in: 
                episode_frames += 1
                episode_reward += processed_reward
                episode_raw_reward += with_explore_reward
                episode_no_explore_reward += no_explore_reward
                if episode_frames > max_episode_length:
                    done = True

            if done:
                need_to_reset = env.lives() == 0 or episode_frames > max_episode_length
                # adding last frame only to save last state
                last_frame = self.atari_processor.process_state_for_memory(state)
                # action, reward, done doesn't matter here
                self.memory.append(last_frame, action, 0, done)
                if not burn_in:
                    avg_target_value = episode_target_value / episode_frames
                    print("Train: time %d, episode %d, length %d, reward %.0f, raw_reward %.0f, loss %.4f, target value %.4f, policy step %d, memory cap %d"
                        % (t, idx_episode, episode_frames, episode_reward, episode_raw_reward, episode_loss, 
                        avg_target_value, self.policy.step, self.memory.current))
                    sys.stdout.flush()
                    save_scalar(idx_episode, 'episode/frames', episode_frames, writer)
                    save_scalar(idx_episode, 'episode/reward', episode_reward, writer)
                    save_scalar(idx_episode, 'episode/raw_reward', episode_raw_reward, writer)
                    save_scalar(idx_episode, 'episode/no_explore_reward', episode_no_explore_reward, writer)
                    save_scalar(idx_episode, 'episode/loss', episode_loss, writer)
                    save_scalar(idx_episode, 'avg/reward', episode_reward / episode_frames, writer)
                    save_scalar(idx_episode, 'avg/target_value', avg_target_value, writer)
                    save_scalar(idx_episode, 'avg/loss', episode_loss / episode_frames, writer)
                    episode_frames = 0
                    episode_reward = .0
                    episode_raw_reward = .0
                    episode_no_explore_reward = .0
                    episode_loss = .0
                    episode_target_value = .0
                    idx_episode += 1
                burn_in = (t < self.num_burn_in)
                if need_to_reset:
                    state = env.reset()
                    self.atari_processor.reset()
                    self.history_processor.reset()

            if not burn_in:
                if t % self.train_freq == 0:
                    loss, target_value = self.update_policy(current_sample)
                    episode_loss += loss
                    episode_target_value += target_value
                # update freq is based on train_freq
                if t % (self.train_freq * self.target_update_freq) == 0:
                    self.target_network.set_weights(self.q_network.get_weights())
                if t % self.save_freq == 0:
                    self.save_model(idx_episode)
                if t % (self.eval_freq * self.train_freq) == 0:
                    episode_raw_reward, episode_reward_std = self.evaluate(env, 20, max_episode_length, False)
                    save_scalar(t, 'eval/episode_raw_reward', episode_raw_reward, writer)
                    save_scalar(t, 'eval/episode_reward_std', episode_reward_std, writer)

        self.save_model(idx_episode)


    def save_model(self, idx_episode):
        safe_path = self.output_path + "/qnet" + str(idx_episode) + ".h5"
        self.q_network.save_weights(safe_path)
        print("Network at", idx_episode, "saved to:", safe_path)

    def evaluate(self, env, num_episodes, max_episode_length=None, monitor=True):
        """Test your agent with a provided environment.
        
        You shouldn't update your network parameters here. Also if you
        have any layers that vary in behavior between train/test time
        (such as dropout or batch norm), you should set them to test.

        Basically run your policy on the environment and collect stats
        like cumulative reward, average episode length, etc.

        You can also call the render function here if you want to
        visually inspect your policy.
        """
        print("Evaluation starts.")

        is_training = False
        if self.load_network:
            self.q_network.load_weights(self.load_network_path)
            print("Load network from:", self.load_network_path)
        if monitor:
            env = wrappers.Monitor(env, self.output_path, video_callable=lambda x:True)
        state = env.reset()

        idx_episode = 1
        episode_frames = 0
        episode_reward = np.zeros(num_episodes)
        t = 0

        while idx_episode <= num_episodes:
            t += 1
            history = self.history_processor.process_state_for_network(
                self.atari_processor.process_state_for_network(state))
            action_state = history[:, :, -self.num_frames:]
            action = self.select_action(action_state, is_training, policy_type = 'GreedyEpsilonPolicy')
            state, reward, done, info = env.step(action)
            episode_frames += 1
            episode_reward[idx_episode-1] += reward 
            if episode_frames > max_episode_length:
                done = True
            if done:
                print("Eval: time %d, episode %d, length %d, reward %.0f" %
                    (t, idx_episode, episode_frames, episode_reward[idx_episode-1]))
                sys.stdout.flush()
                state = env.reset()
                episode_frames = 0
                idx_episode += 1
                self.atari_processor.reset()
                self.history_processor.reset()

        reward_mean = np.mean(episode_reward)
        reward_std = np.std(episode_reward)
        print("Evaluation summury: num_episodes [%d], reward_mean [%.3f], reward_std [%.3f]" %
            (num_episodes, reward_mean, reward_std))
        sys.stdout.flush()

        return reward_mean, reward_std
