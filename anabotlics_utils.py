import os
import sys
import csv
import requests
import json
import threading
import configparser
from datetime import datetime
import functools

import tqdm
import praw
import firebase_admin
from firebase_admin import firestore
from google.cloud import storage

import os
os.environ.setdefault("GCLOUD_PROJECT", "anabotlics-reddit-bot")
BUCKET = os.environ.get('BUCKET', 'anabotlics-cf-data')
STORAGE_CLIENT = None
APP = None
DB = None

THE_MONKEYS = {
'geardedandbearded','shrugsandsnugs',
'automoderator', 'steroidsbot',
'calllivesmatter', 'olvankarr', 'accountunkn0wn'
}


def init_storage_client():
    global STORAGE_CLIENT

    STORAGE_CLIENT = storage.Client()


def init_firestore():
    global APP
    global DB

    APP = firebase_admin.initialize_app()
    DB = firestore.client()


def get_gs_file(bucket: str, fpath: str) -> str:
    """ Returns content of gcs file as string """
    if STORAGE_CLIENT is None:
        init_storage_client()

    bucket = STORAGE_CLIENT.bucket(bucket)
    blob = bucket.blob(fpath)
    with blob.open('r') as fd:
        content = fd.read()
    return content


def get_bot_init(bucket: str, fpath: str) -> configparser.ConfigParser:
    """ Reads .ini config file from GCS and returns a ConfigParser """
    config_file = get_gs_file(bucket, fpath)
    config = configparser.ConfigParser()
    config.read_string(config_file)
    return config


def unsticky_previous(title: str, bot: praw.models.Subreddit):
    """ Searches for previous thread to unsticky within the last 150 posts """

    limit = 150
    found_submission = None
    generator = bot.hot()
    count = 0
    while count < limit and found_submission is None:
        try:
            s = next(generator)
        except StopIteration:
            print('No previous stickied thread found')
            break
        if s.title.startswith(title) and s.stickied:
            found_submission = s
            found_submission.mod.sticky(state=False)
            print('Found submission stickied and unstickied it')
        count += 1


def get_body(config: dict) -> str:
    """
    Returns body_text set in config or
    reads body_file from GCS and return its content
    """

    post_data = config['post']
    if post_data.get('body_text'):
        body = post_data['body_text']
    elif post_data.get('body_file'):
        body = get_gs_file(config['bucket'], post_data['body_file'])
    else:
        raise Exception(f"Malformed config for {post_data['title']}")
    return body


def get_flair_from_text(bot: praw.models.Subreddit, flair_text: str) -> str:
    """ Searches for flair text within subreddit's flairs and returns its id """

    flair_choices = bot.flair.link_templates.user_selectable()
    try:
        flair = next(
            flair for flair in flair_choices
            if flair['flair_text'].lower() == flair_text.lower()
        )
        return flair['flair_template_id']
    except StopIteration:
        print(f"Thread not flaired, flair {flair_text} could not be found")

    return None


@functools.cache
def record_user(name, uid):
    if DB is None:
        init_firestore()

    doc_ref = DB.collection(u'users').document(uid)
    doc_ref.set({
        'name': name
    })
    return 1


def init_reddit_bot(config):
    reddit = praw.Reddit(
        client_id=config.get('DEFAULT', 'CLIENT_ID'),
        client_secret=config.get('DEFAULT', 'CLIENT_SECRET'),
        username=config.get('DEFAULT', 'USERNAME'),
        password=config.get('DEFAULT', 'PASSWORD'),
        user_agent=config.get('DEFAULT', 'USER_AGENT')
    )
    return reddit

def get_config(event):
    try:
        gcs_config_path = event['attributes']['gcs_config_path']
        if gcs_config_path.startswith("gs://"):
            gcs_config_path = gcs_config_path[5:]
        bucket, *config_fpath = gcs_config_path.split('/')
        config_fpath = '/'.join(config_fpath)
    except Exception:
        raise Exception("Cannot extract config path frrom gcs_config_path in the event sent to the bot. Check the trigger and make sure it has the `gcs_config_path` attribute set with the path to the json config file in google cloud storage.")
    config = get_bot_init(bucket, config_fpath)
    return config
