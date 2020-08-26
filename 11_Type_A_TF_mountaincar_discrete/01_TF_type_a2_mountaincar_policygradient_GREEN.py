import gym
import tensorflow as tf
import numpy as np
import time, datetime
import pylab
import sys
import pickle
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
from tensorflow.python.framework import ops
ops.reset_default_graph()

env_name = 'MountainCar-v0'
# set environment
env = gym.make(env_name)
env.seed(1)     # reproducible, general Policy gradient has high variance
env = env.unwrapped

# get size of state and action from environment
state_size = env.observation_space.shape[0]
action_size = env.action_space.n

game_name =  sys.argv[0][:-3]

model_path = "save_model/" + game_name
graph_path = "save_graph/" + game_name

# Make folder for save data
if not os.path.exists(model_path):
    os.makedirs(model_path)
if not os.path.exists(graph_path):
    os.makedirs(graph_path)
    
    
# This is REINFORCE agent for the Cartpole
class PolicyGradient:
    def __init__(self, sess, state_size, action_size):
        self.sess = sess
        # if you want to see Cartpole learning, then change to True
        self.render = False
        # get size of state and action
        self.state_size = state_size
        self.action_size = action_size
        
        # train time define
        self.training_time = 40*60
        
        # these is hyper parameters for the PolicyGradient
        self.learning_rate = 0.001
        self.discount_factor = 0.99
        
        self.step = 0
        self.episode = 0
        
        self.hidden1, self.hidden2 = 64, 64
        
        self.ep_trial_step = 10000
        # lists for the states, actions and rewards
        self.buffer_state, self.buffer_action, self.buffer_reward = [], [], []
        
        self._init_input()
        self.build_model()
        self._init_op()

    def _init_input(self):
        # with tf.variable_scope('input'):
        self.state = tf.placeholder(tf.float32,  [None, self.state_size], name='state')
        self.action = tf.placeholder(tf.float32, [None, self.action_size], name="action")
        self.reward = tf.placeholder(tf.float32, name="reward")

    # approximate policy and value using Neural Network
    # actor -> state is input and probability of each action is output of network
    def build_model(self):

        w_init, b_init = tf.random_normal_initializer(mean=0, stddev=0.3), tf.constant_initializer(0.1)
        # fc1
        actor_hidden = tf.layers.dense(inputs=self.state, units = self.hidden1, activation=tf.nn.tanh,  # tanh activation
            kernel_initializer = w_init, bias_initializer = b_init, name='fc1_a')
        # fc2
        actor_predict = tf.layers.dense(inputs=actor_hidden, units = self.action_size, activation=None,
            kernel_initializer = w_init, bias_initializer = b_init, name='fc2_a')

        self.policy = tf.nn.softmax(actor_predict, name='act_prob')  # use softmax to convert to probability
        
    def _init_op(self):
        # with tf.variable_scope('actor_loss'):
        self.log_p = self.action * tf.log(self.policy)
        self.log_lik = self.log_p * self.reward
        self.actor_loss = tf.reduce_mean(tf.reduce_sum(-self.log_lik, axis=1))
        
        # with tf.variable_scope('train'):
        self.train_op = tf.train.AdamOptimizer(self.learning_rate).minimize(self.actor_loss)
        
    # get action from policy network
    def get_action(self, state):
        # Reshape observation to (num_features, 1)
        state_t = np.reshape(state, [1, self.state_size])
        # Run forward propagation to get softmax probabilities
        prob_weights = self.sess.run(self.policy, feed_dict={self.state: state_t})

        # Select action using a biased sample
        # this will return the index of the action we've sampled
        action = np.random.choice(np.arange(self.action_size), p=prob_weights[0])

        return action
        
    # calculate discounted rewards
    def discount_and_norm_rewards(self):
        buffer_reward = np.vstack(self.buffer_reward)
        discounted_rewards = np.zeros_like(buffer_reward)
        running_add = 0
        for index in reversed(range(0, len(buffer_reward))):
            running_add = running_add * self.discount_factor + buffer_reward[index]
            discounted_rewards[index] = running_add
            
        # normalize episode rewards
        discounted_rewards -= np.mean(discounted_rewards)
        discounted_rewards /= np.std(discounted_rewards)
        return discounted_rewards
    
    # save <s, a ,r> of each step
    # this is used for calculating discounted rewards
    def append_sample(self, state, action, reward):
        # Store actions as list of arrays
        # e.g. for action_size = 2 -> [ array([ 1.,  0.]), array([ 0.,  1.]), array([ 0.,  1.]), array([ 1.,  0.]) ]
        action_array = np.zeros(self.action_size)
        action_array[action] = 1
        
        self.buffer_state.append(state)
        self.buffer_action.append(action_array)
        self.buffer_reward.append(reward)
        
    # update policy network and value network every episode
    def train_model(self):
        discounted_rewards = self.discount_and_norm_rewards()
                    
        feed_dict={
            self.state: np.vstack(self.buffer_state),
            self.action: np.vstack(self.buffer_action),
            self.reward: discounted_rewards,
        }
        
        actor_loss,_ = self.sess.run([self.actor_loss, self.train_op], feed_dict)
        
        self.buffer_state, self.buffer_action, self.buffer_reward = [], [], []
        
    def save_model(self):
        # Save the variables to disk.
        save_path = self.saver.save(self.sess, model_path + "/model.ckpt")
        save_object = (self.episode, self.step)
        with open(model_path + '/epsilon_episode.pickle', 'wb') as ggg:
            pickle.dump(save_object, ggg)

        print("\n Model saved in file: %s" % model_path)

def main():
    with tf.Session() as sess:
        # sess = tf.Session()
        agent = PolicyGradient(sess, state_size, action_size)

        init = tf.global_variables_initializer()
        agent.saver = tf.train.Saver()
        ckpt = tf.train.get_checkpoint_state(model_path)

        if ckpt and tf.train.checkpoint_exists(ckpt.model_checkpoint_path):
            agent.saver.restore(agent.sess, ckpt.model_checkpoint_path)
            if os.path.isfile(model_path + '/epsilon_episode.pickle'):

                with open(model_path + '/epsilon_episode.pickle', 'rb') as ggg:
                    agent.episode, agent.step = pickle.load(ggg)

            print('\n\n Variables are restored!')

        else:
            agent.sess.run(init)
            print('\n\n Variables are initialized!')

        avg_score = 10000
        episodes, scores = [], []

        # start training    
        # Step 3.2: run the game
        display_time = datetime.datetime.now()
        print("\n\n",game_name, "-game start at :",display_time,"\n")
        start_time = time.time()
        
        while time.time() - start_time < agent.training_time and avg_score > 200:
            
            state = env.reset()
            done = False
            score = 10000
            ep_step = 0

            while not done and ep_step < agent.ep_trial_step:
                # fresh env
                ep_step += 1
                agent.step += 1

                # Select action_arr
                action = agent.get_action(state)

                # run the selected action_arr and observe next state and reward
                next_state, reward, done, _ = env.step(action) 

                # save the sample <state, action, reward> to the memory
                agent.append_sample(state, action, reward)

                score = ep_step

                state = next_state

                if done or ep_step == agent.ep_trial_step:
                    agent.episode += 1
                    agent.train_model()

                    scores.append(score)
                    episodes.append(agent.episode)
                    avg_score = np.mean(scores[-min(30, len(scores)):])

                    print('episode :{:>6,d}'.format(agent.episode),'/ ep step :{:>5,d}'.format(ep_step), \
                          '/ time step :{:>8,d}'.format(agent.step),'/ last 30 avg :{:> 4.1f}'.format(avg_score) )

                    break
        # Save model
        agent.save_model()

        pylab.plot(episodes, scores, 'b')
        pylab.savefig("./save_graph/mountaincar_PG_2.png")

        e = int(time.time() - start_time)
        print(' Elasped time :{:02d}:{:02d}:{:02d}'.format(e // 3600, (e % 3600 // 60), e % 60))
        sys.exit()

if __name__ == "__main__":
    main()
