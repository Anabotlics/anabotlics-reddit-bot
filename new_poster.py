import os
import json
import configparser
from datetime import datetime
import functools

import praw
import firebase_admin
from firebase_admin import firestore
from google.cloud import storage

import anabotlics_utils

APP = None
DB = None


@anabotlics_utils.conditional_cache
def check_known_user(commenter_id):
    print(f"Checking {commenter_id}")
    ref = DB.collection(u'users').document(commenter_id).get()
    # Second value used by cache to only cache the call if the user exists
    return (ref.exists, ref.exists)


@functools.cache
def record_user(name, uid):
    doc_ref = DB.collection(u'users').document(uid)
    doc_ref.set({
        'name': name
    })
    return 1


def init_firestore():
    global APP
    global DB

    APP = firebase_admin.initialize_app()
    DB = firestore.client()


def main(event, *args, **kwargs):
    init_firestore()

    config = anabotlics_utils.get_config(event)
    reddit = anabotlics_utils.init_reddit_bot(config)
    anabotlics_bot = reddit.subreddit('steroids')
    print(f"Bot initialized on subreddit {config.get('DEFAULT', 'SUBREDDIT')}")

    welcome_text = anabotlics_utils.get_gs_file(bucket, config.get('DEFAULT', 'welcome_file'))
    for comment in anabotlics_bot.stream.comments(skip_existing=True):
        print(f"Processing {comment.author.name}: {comment.body}")

        commenter_id = comment.author.id
        known_user = check_known_user(commenter_id)

        if not known_user:
            anabotlics_utils.record_user(comment)
            comment.reply(welcome_text)

main({'attributes': {'gcs_config_path': 'anabotlics-cf-data/bot.ini'}})
