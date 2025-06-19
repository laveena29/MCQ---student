import torch
import torch.nn as nn
import torch.optim as optim
import random
import numpy as np
from collections import deque

class DQN(nn.Module):
    def __init__(self, state_size, action_size):
        super(DQN, self).__init__()
        self.fc1 = nn.Linear(state_size, 64)
        self.fc2 = nn.Linear(64, 64)
        self.out = nn.Linear(64, action_size)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.out(x)


class DQNAgent:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.memory = deque(maxlen=1000)
        self.gamma = 0.95
        self.epsilon = 1.0
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.01
        self.model = DQN(state_size, action_size)
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()

    def act(self, state):
        if np.random.rand() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            q_values = self.model(state_tensor)
        return torch.argmax(q_values[0]).item()

    def remember(self, state, action, reward, next_state):
        self.memory.append((state, action, reward, next_state))

    def replay(self, batch_size=32):
        if len(self.memory) < batch_size:
            return

        batch = random.sample(self.memory, batch_size)
        for state, action, reward, next_state in batch:
            state_tensor = torch.FloatTensor(state)
            target = reward
            if next_state is not None:
                target = reward + self.gamma * torch.max(self.model(torch.FloatTensor(next_state)))

            current_qs = self.model(state_tensor)
            target_qs = current_qs.clone().detach()
            target_qs[action] = target

            loss = self.criterion(current_qs, target_qs)

            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def compute_reward(self, performance_map, action):
        """
        Custom reward function to focus on weak areas.
        """
        chapter, difficulty = self.decode_action(action)

        # Check performance for the current chapter and difficulty
        correct = performance_map.get(chapter, {}).get(difficulty, 0)
        total = sum(performance_map.get(chapter, {}).values()) or 1
        score = correct / total  # Calculate score for that difficulty in that chapter

        # Reward is higher if user is weak in that area (i.e., correct answers are low)
        if score < 0.5:
            reward = 1  # Positive reward for focusing on weak areas
        else:
            reward = -1  # Negative reward for overfocusing on strong areas

        return reward

    def decode_action(self, action):
        chapter = action // 3 + 1
        difficulty = ['easy', 'medium', 'hard'][action % 3]
        return chapter, difficulty

    def save(self, path='dqn_model.pth'):
        torch.save(self.model.state_dict(), path)

    def load(self, path='dqn_model.pth'):
        try:
            self.model.load_state_dict(torch.load(path))
            self.model.eval()
            print("[INFO] DQN model loaded.")
        except FileNotFoundError:
            print("[INFO] No existing DQN model found, starting fresh.")
