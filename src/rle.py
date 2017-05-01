from rle_python_interface.rle_python_interface import RLEInterface
from random import randrange
import numpy as np
import imageio
import pickle

class actionSet:
    def __init__(self, rle): 
        self.minimal_actions = rle.getMinimalActionSet()
        self.n = len(self.minimal_actions)
    
    def sample(self):
        return randrange(len(self.minimal_actions))
    
class rle:
    def __init__(self, rom, core = 'snes', skip_mean = 7, record = False, path=""):
        self.rle = RLEInterface()
        self.rle.loadROM(rom, core)
        self.action_space = actionSet(self.rle)
        self.skip_mean = skip_mean
        self.path = path
        self.record = record
        if self.record:
            self.idx_video = 0

    def reset(self):
        self.rle.reset_game()
        # noop
        num_noop = randrange(30)
        for i in range(num_noop):
            self.rle.act(0)

        state = self.rle.getScreenRGB()
        if self.record:
            if self.idx_video > 0 and not self.writer.closed:
                self.writer.close()
                with open(self.trace_path, 'wb') as tdump:
                    pickle.dump(self.trace, tdump)
            self.idx_video += 1
            filename = "%s/video-%05d.mp4" % (self.path, self.idx_video)
            self.writer = imageio.get_writer(filename, fps=20, codec = "mpeg4")
            self.writer.append_data(state)
            self.trace_path = "%s/trace-%05d.dmp" % (self.path, self.idx_video)
            self.trace = {"state": [], "reward": [], "action": [], "done": []}
            self.trace["state"].append(state)
        return state

    def step(self, action_ix):
        action = self.action_space.minimal_actions[action_ix]
        reward = 0
        for i in range(randrange(self.skip_mean-1, self.skip_mean+2)):
            reward += self.rle.act(action)
            done = self.rle.game_over()
            if done:
                break
        next_state = self.rle.getScreenRGB()
        if self.record:
            self.writer.append_data(next_state)
            self.trace["state"].append(next_state)
            self.trace["reward"].append(reward)
            self.trace["action"].append(action_ix)
            self.trace["done"].append(reward)
        return next_state, reward, done, ''

    def seed(self, s):
        self.rle.setInt('random_seed', s)
