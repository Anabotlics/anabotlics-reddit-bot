import json
import configparser
from datetime import datetime

import praw
from google.cloud import storage

import anabotlics_utils


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


def main(event: dict, *args, **kwargs):
    config = anabotlics_utils.get_config(event)
    reddit = anabotlics_utils.init_reddit_bot(config)
    anabotlics_bot = reddit.subreddit('steroids')

    # Extract thread details
    title = thread_config['post']['title']
    if '%' in title:
        now = datetime.now()
        title = now.strftime(title)

    body = get_body(thread_config)

    # Get flair if specified
    if thread_config['post'].get('flair_id'):
        flair = thread_config['post'].get('flair_id')
    elif thread_config['post'].get('flair_text'):
        flair = get_flair_from_text(
            anabotlics_bot, thread_config['post']['flair_text']
        )
    else:
        flair = None

    sticky = thread_config['post'].get('sticky')
    print(f"Attempting to post {'S' if sticky else 'X'} [{flair}] {title}: {body[:200]}...")
    if sticky:
        # Use first half of title if string_match not specified
        # This is to find the previous thread to unsticky
        string_match = thread_config['post'].get(
            'string_match', title[:len(title)//2]
        )
        unsticky_previous(string_match, anabotlics_bot)
        submission = anabotlics_bot.submit(
            title=title,
            selftext=body,
            flair_id=flair
        )
        submission.mod.sticky(state=True)
    else:
        submission = anabotlics_bot.submit(
            title=title,
            selftext=body,
            flair_id=flair
        )

    print(f"Posted: {submission.url}")
