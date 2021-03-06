from os.path import exists
from typing import Optional, List, Dict, Tuple
from json import dumps, loads

from telegram import User, Update, Message, Bot
from telegram.ext import CallbackContext

from json_objects import convert_to_dict
import logging


class State:
    def __init__(self, path="state.json"):
        self._path = path
        self._challenge: Optional[List[str]] = None
        self._challenge_from: Optional[int] = None
        self._listen_to: List[int] = []
        self._admins: [str] = []
        self._highscore: Dict[str, Tuple[str, int]] = {}
        self._load()

    def check_admin(self, user: User):
        return len(self._admins) == 0 or f"@{user.username}" in self._admins

    def add_admin(self, username: str):
        if username is None or len(username) == 0:
            return
        if username not in self._admins:
            self._admins.append(username)
            self._store()

    def del_admin(self, username: str):
        if username in self._admins:
            self._admins.remove(username)
            self._store()

    def get_admin_state(self):
        if len(self._admins) == 0:
            return "Everyone is admin"
        else:
            return f"Current admins: {', '.join(self._admins)}"

    def check_answer(self, update: Update, context: CallbackContext):
        msg: Message = update.message

        if msg is None or msg.chat_id not in self._listen_to:
            return

        text: str = msg.text
        if text is None or self._challenge is None:
            return
        text = text.lower()

        found = False
        for group in self._challenge:
            elements: [str] = [x.strip() for x in group.split(",")]
            if all((e in text) for e in elements):
                found = True
                break

        if not found:
            return

        if self.is_challenge_from(msg.from_user):
            context.bot.send_message(msg.chat_id, f"You are the current user, this is not allowed! Reset.")
            self._challenge = None
            self._challenge_from = None
            self._store()
            return

        high = self._add_highscore(msg.from_user)
        for cid in self._listen_to:
            context.bot.send_message(cid, f"{str(msg.from_user.first_name)} ({high}) got it: {' or '.join(self._challenge)}")

        self._challenge = None
        self._challenge_from = msg.from_user.id
        self._store()

    def new_challenge(self, update: Update, context: CallbackContext):
        msg: Message = update.message
        bot: Bot = context.bot
        if not state.is_challenge_from(msg.from_user):
            context.bot.send_message(msg.chat_id, f"You are not the current user!")
            return
        msg_type: str = msg.chat.type  # 'private', 'group', 'supergroup' or 'channel'
        if msg_type != "private":
            bot.send_message(msg.chat_id, f"The command has to be executed in a private channel!")
            return

        self._challenge_from = msg.from_user.id

        if self._listen_to is None or len(self._listen_to) == 0:
            bot.send_message(msg.chat_id, "Please set listen_to first.")
            return

        if self._challenge is not None:
            bot.send_message(msg.chat_id, "Challenge already active ..")
            return

        txt: str = update.message.caption
        txt = txt[len('/new'):].strip()
        self._challenge = list(filter(lambda s: len(s) != 0, [x.lower().strip() for x in txt.split(";")]))
        for cid in self._listen_to:
            bot.send_photo(cid, msg.photo[0].file_id, caption=f"Your next challenge from {msg.from_user.first_name} ... good luck :)")

        self._store()

    def skip(self, update: Update, context: CallbackContext):
        msg: Message = update.message

        if not self.is_challenge_from(msg.from_user) and not self.check_admin(msg.from_user):
            context.bot.send_message(msg.chat_id, f"You are not the current user!")
            return

        if self._challenge is None:
            context.bot.send_message(msg.chat_id, "Skipped. Everyone can create a new challenge now ..")
            self._challenge_from = None

        else:
            context.bot.send_message(msg.chat_id, f"No one got it: {' or '.join(self._challenge)}")
            self._challenge = None
            self._challenge_from = None

        self._store()

    def is_challenge_from(self, from_user: User):
        if self._challenge_from is None:
            return True
        if from_user is None:
            return False
        return self._challenge_from == from_user.id

    def update_listen_to(self, chat_id):
        if chat_id in self._listen_to:
            self._listen_to.remove(chat_id)
        else:
            self._listen_to.append(chat_id)
        self._store()
        return chat_id in self._listen_to

    def get_hs(self) -> str:
        vals = list(self._highscore.values())
        vals.sort(key=lambda v: v[1], reverse=True)
        hs = "\n".join(map(lambda t: f"{t[0]}: {t[1]}", vals))
        return hs

    def __repr__(self):
        return f"Current Challenge: {self._challenge} from {self._challenge_from}. Current Admins: [{', '.join(self._admins)}]"

    def _store(self):
        with open(self._path, "w", encoding="utf-8-sig") as outfile:
            outfile.write(dumps(self, default=convert_to_dict, indent=4))

    def _load(self):
        if not exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8-sig") as jsonfile:
                loaded = loads(jsonfile.read())
                self._path = loaded["_path"]
                self._challenge = loaded["_challenge"]
                self._challenge_from = loaded["_challenge_from"]
                self._listen_to = loaded["_listen_to"]
                self._admins = loaded["_admins"]
                self._highscore = loaded["_highscore"]
        except Exception:
            logging.error("State could not be loaded!")

    def _add_highscore(self, from_user: User) -> str:
        key = str(from_user.id)
        if key in self._highscore.keys():
            (name, hs) = self._highscore[key]

            hs = int(hs) + 1
            self._highscore[key] = (from_user.first_name, hs)
        else:
            self._highscore[key] = (from_user.first_name, 1)

        return f"Highscore: {self._highscore[key][1]}"


state: State = State()
