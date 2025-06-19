import numpy as np

class QuizEnv:
    def __init__(self, chapter_count=6):
        self.chapter_count = chapter_count
        self.action_space = chapter_count * 3  # 6 chapters * 3 difficulty levels
        self.state = None

    def get_state(self, performance):
        """
        Generates a state vector from the user performance.
        The state vector will represent the user's performance in each chapter and difficulty.
        The format will be:
        [chapter_1_easy_percentage, chapter_1_medium_percentage, chapter_1_hard_percentage, 
        chapter_2_easy_percentage, chapter_2_medium_percentage, chapter_2_hard_percentage, ...]
        """
        state = []
        for chapter_id in range(1, self.chapter_count + 1):
            # Performance data for the chapter, default to 0 if not available
            stats = performance.get(chapter_id, {'easy': 0, 'medium': 0, 'hard': 0})
            
            # Normalize the data to avoid division by zero
            total = sum(stats.values()) or 1  # Avoid division by zero
            state.extend([ 
                stats['easy'] / total,   # Easy difficulty performance
                stats['medium'] / total, # Medium difficulty performance
                stats['hard'] / total    # Hard difficulty performance
            ])
        self.state = np.array(state)
        return self.state

    def decode_action(self, action):
        """
        Converts the action (which is an integer) into a chapter and difficulty.
        For example, if action = 0, it could be chapter 1, easy. 
        If action = 1, it could be chapter 1, medium, etc.
        """
        chapter = action // 3 + 1
        difficulty = ['easy', 'medium', 'hard'][action % 3]
        return chapter, difficulty

    def encode_action(self, chapter, difficulty):
        """ Encodes chapter and difficulty into an action number """
        difficulty_map = {'easy': 0, 'medium': 1, 'hard': 2}
        return (chapter - 1) * 3 + difficulty_map[difficulty]
