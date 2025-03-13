import sqlite3
from datetime import datetime
from config import DATABASE 
import os
import cv2
import numpy as np
from math import sqrt, ceil, floor
import discord

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute(''' 
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT,
                bonus_points INTEGER DEFAULT 0
            )
            ''')

            conn.execute(''' 
            CREATE TABLE IF NOT EXISTS prizes (
                prize_id INTEGER PRIMARY KEY,
                image TEXT,
                used INTEGER DEFAULT 0
            )
            ''')

            conn.execute(''' 
            CREATE TABLE IF NOT EXISTS winners (
                user_id INTEGER,
                prize_id INTEGER,
                win_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
            )
            ''')

            conn.commit()

    def add_user(self, user_id, user_name):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT INTO users (user_id, user_name) VALUES (?, ?)', (user_id, user_name))
            conn.commit()

    def add_prize(self, data):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.executemany('INSERT INTO prizes (image) VALUES (?)', data)
            conn.commit()

    def add_winner(self, user_id, prize_id):
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor() 
            cur.execute('SELECT * FROM winners WHERE user_id = ? AND prize_id = ?', (user_id, prize_id))
            if cur.fetchall():
                return 0
            else:
                conn.execute('INSERT INTO winners (user_id, prize_id, win_time) VALUES (?, ?, ?)', (user_id, prize_id, win_time))
                self.add_bonus_points(user_id, 10)  # Her kazanan kullanıcıya bonus puan ekleniyor
                conn.commit()
                return 1

    def add_bonus_points(self, user_id, points):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('UPDATE users SET bonus_points = bonus_points + ? WHERE user_id = ?', (points, user_id))
            conn.commit()

    def get_users(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM users')
            return [x[0] for x in cur.fetchall()]

    def get_prize_img(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT image FROM prizes WHERE prize_id = ?', (prize_id,))
            return cur.fetchall()[0][0]

    def get_random_prize(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM prizes WHERE used = 0 ORDER BY RANDOM()')
            return cur.fetchall()[0]

    def get_winners_count(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute(''' SELECT COUNT(*) FROM winners WHERE prize_id = ? ''', (prize_id,))
            return cur.fetchone()[0]

    def get_rating(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute(''' 
                SELECT users.user_name, COUNT(winners.user_id) AS total_wins
                FROM users
                LEFT JOIN winners ON users.user_id = winners.user_id
                GROUP BY users.user_id
                ORDER BY total_wins DESC
                LIMIT 10
            ''')
            return cur.fetchall()

    def get_winners_img(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute(''' 
                SELECT image FROM winners
                INNER JOIN prizes ON winners.prize_id = prizes.prize_id
                WHERE user_id = ? 
            ''', (user_id,))
            return cur.fetchall()

    def get_user_bonus_points(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT bonus_points FROM users WHERE user_id = ?', (user_id,))
            return cur.fetchone()[0]

    def use_bonus_points(self, user_id, points):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('UPDATE users SET bonus_points = bonus_points - ? WHERE user_id = ?', (points, user_id))
            conn.commit()

    def is_user_admin(self, user_id, bot):
        """Check if a user has the Administrator role."""
        member = bot.get_user(user_id)
        if member:
            for role in member.roles:
                if role.permissions.administrator:
                    return True
        return False

def hide_img(img_name):
    image = cv2.imread(f'img/{img_name}')
    blurred_image = cv2.GaussianBlur(image, (15, 15), 0)
    pixelated_image = cv2.resize(blurred_image, (30, 30), interpolation=cv2.INTER_NEAREST)
    pixelated_image = cv2.resize(pixelated_image, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f'hidden_img/{img_name}', pixelated_image)

def create_collage(image_paths):
    images = []
    for path in image_paths:
        image = cv2.imread(path)
        images.append(image)

    num_images = len(images)
    num_cols = floor(sqrt(num_images))
    num_rows = ceil(num_images / num_cols)

    collage = np.zeros((num_rows * images[0].shape[0], num_cols * images[0].shape[1], 3), dtype=np.uint8)

    for i, image in enumerate(images):
        row = i // num_cols
        col = i % num_cols
        collage[row * image.shape[0]:(row + 1) * image.shape[0], col * image.shape[1]:(col + 1) * image.shape[1], :] = image

    return collage

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()
    prizes_img = os.listdir('img')
    data = [(x,) for x in prizes_img]
    manager.add_prize(data)
