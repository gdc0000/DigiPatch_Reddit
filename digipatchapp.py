import streamlit as st
import datetime
import pandas as pd
import praw
from praw.exceptions import APIException
import prawcore
import time

def add_footer():
    st.markdown("---")
    st.markdown("### **Gabriele Di Cicco, PhD in Social Psychology**")
    st.markdown("""
    [GitHub](https://github.com/gdc0000) | 
    [ORCID](https://orcid.org/0000-0002-1439-5790) | 
    [LinkedIn](https://www.linkedin.com/in/gabriele-di-cicco-124067b0/)
    """)

def initialize_reddit(client_id, client_secret, username, password):
    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            password=password,
            user_agent="web_app",
            username=username,
            check_for_async=False
        )
        if reddit.read_only:
            st.error("Authentication failed: Reddit is in read-only mode.")
        return reddit
    except Exception as e:
        st.error(f"Error initializing Reddit: {e}")
        return None

def adaptive_sleep(retry_count, wait_multiplier=5):
    """
    Adaptive sleep function that waits longer on each retry.
    """
    wait_time = wait_multiplier * (retry_count + 1)
    st.warning(f"Rate limit reached. Waiting {wait_time} seconds before retrying...")
    time.sleep(wait_time)

def collect_reddit_data(
    reddit,
    subreddits,
    sorting_methods,
    post_limit,
    collect_comments,
    sleep_time,
    comment_method=None,
    comment_limit=None,
    comment_min=None,
    comment_max=None
):
    # Retrieve previously collected data from session_state if available.
    if "collected_data" not in st.session_state:
        st.session_state["collected_data"] = []
    collected_data = st.session_state["collected_data"]

    # Determine total iterations (only if a fixed post_limit is set).
    if post_limit is not None:
        total_iterations = len(subreddits) * len(sorting_methods) * post_limit
    else:
        total_iterations = None

    progress_bar = st.progress(0) if total_iterations is not None else None
    progress_text = st.empty() if total_iterations is None else None
    current_iteration = 0

    # Iterate over each subreddit.
    for subreddit_name in subreddits:
        try:
            subreddit = reddit.subreddit(subreddit_name)
        except Exception as e:
            st.error(f"Error accessing subreddit {subreddit_name}: {e}")
            continue

        # Iterate over each selected sorting method.
        for sorting_method in sorting_methods:
            st.write(f"Collecting posts from **r/{subreddit_name}** sorted by **{sorting_method}**...")
            try:
                posts_generator = getattr(subreddit, sorting_method)(limit=post_limit)
            except Exception as e:
                st.error(f"Error fetching posts for r/{subreddit_name} using {sorting_method}: {e}")
                continue

            max_retries = 5  # Maximum number of retries for rate-limit errors
            retry_count = 0
            while True:
                try:
                    post = next(posts_generator)
                    # Reset retry counter upon successful retrieval.
                    retry_count = 0
                except StopIteration:
                    # No more posts in this generator.
                    break
                except prawcore.exceptions.TooManyRequests as e:
                    # Handle HTTP 429 errors (Too Many Requests)
                    if retry_count < max_retries:
                        adaptive_sleep(retry_count)
                        retry_count += 1
                        continue
                    else:
                        st.error(f"Skipping posts from r/{subreddit_name} sorted by {sorting_method} after repeated rate limiting.")
                        break
                except Exception as e:
                    st.error(f"Unexpected error retrieving a post in r/{subreddit_name}: {e}")
                    break

                try:
                    # Retrieve post-level details.
                    post_id = post.id
                    post_title = post.title
                    post_author = str(post.author)
                    post_score = post.score
                    post_num_comments = post.num_comments
                    post_upvote_ratio = post.upvote_ratio
                    post_url = post.url
                    post_timestamp = datetime.datetime.utcfromtimestamp(post.created_utc)

                    if collect_comments:
                        # Retrieve comments with retry logic for rate-limit errors.
                        comment_retry = 0
                        max_comment_retries = 5
                        while comment_retry < max_comment_retries:
                            try:
                                post.comments.replace_more(limit=0)
                                all_comments = post.comments.list()
                                break
                            except APIException as e:
                                if "429" in str(e):
                                    adaptive_sleep(comment_retry)
                                    comment_retry += 1
                                    continue
                                else:
                                    st.error(f"Error collecting comments for post {post_id} in r/{subreddit_name}: {e}")
                                    all_comments = []
                                    break
                        else:
                            st.error(f"Skipping comments for post {post_id} in r/{subreddit_name} due to repeated rate limiting.")
                            all_comments = []

                        # Decide which comments to include based on the selected method.
                        if comment_method == "Limit":
                            comment_list = all_comments[:comment_limit] if comment_limit else all_comments
                        elif comment_method == "Range":
                            min_index = comment_min - 1 if comment_min else 0  # Convert 1-indexed to 0-indexed.
                            comment_list = all_comments[min_index:comment_max] if comment_max else all_comments[min_index:]
                        elif comment_method == "Maximum":
                            comment_list = all_comments
                        else:
                            comment_list = []

                        if comment_list:
                            # Create one row per comment.
                            for comment in comment_list:
                                comment_author = str(comment.author) if comment.author else None
                                comment_score = comment.score
                                comment_body = comment.body
                                comment_timestamp = datetime.datetime.utcfromtimestamp(comment.created_utc)
                                row = [
                                    subreddit_name, post_id, post_title, post_author, post_score, post_num_comments,
                                    post_upvote_ratio, post_url, post_timestamp, sorting_method,
                                    comment_author, comment_score, comment_body, comment_timestamp
                                ]
                                collected_data.append(row)
                        else:
                            # If no comments are available, record the post with empty comment fields.
                            row = [
                                subreddit_name, post_id, post_title, post_author, post_score, post_num_comments,
                                post_upvote_ratio, post_url, post_timestamp, sorting_method,
                                None, None, None, None
                            ]
                            collected_data.append(row)
                    else:
                        # When comment collection is disabled, record just the post.
                        row = [
                            subreddit_name, post_id, post_title, post_author, post_score, post_num_comments,
                            post_upvote_ratio, post_url, post_timestamp, sorting_method,
                            None, None, None, None
                        ]
                        collected_data.append(row)
                except Exception as e:
                    st.error(f"Unexpected error processing post {post.id if 'post' in locals() else 'Unknown'} in r/{subreddit_name}: {e}")
                    continue

                current_iteration += 1
                if progress_bar is not None:
                    progress_bar.progress(min(current_iteration / total_iterations, 1.0))
                else:
                    progress_text.text(f"Processed {current_iteration} posts...")
                time.sleep(sleep_time)

    st.session_state["collected_data"] = collected_data
    return collected_data

def main():
    st.image("DigiPatchLogo.png", width=700)  # Replace with your logo file path.
    st.title("WP4 DigiPatch: Reddit Data Collection")
    st.markdown("This tool collects Reddit posts and comments across multiple subreddits for analysis. It is designed to handle unexpected events gracefully, allowing you to resume data collection without starting over.")
    st.markdown("https://digipatch.eu/")

    # --- Reddit API Credentials ---
    st.header("Reddit API Credentials")
    client_id = st.text_input("Client ID")
    client_secret = st.text_input("Client Secret")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    # --- Data Collection Parameters ---
    st.header("Subreddit and Data Parameters")
    subreddits_input = st.text_input('Subreddit Names (comma-separated)', '')
    sorting_methods = st.multiselect(
        'Sorting Methods',
        ['hot', 'new', 'top', 'controversial', 'rising'],
        default=['hot']
    )
    
    # Post limit selection: fixed limit or maximum.
    post_limit_option = st.radio("Select Post Limit", options=["Limit", "Maximum"], index=0)
    if post_limit_option == "Limit":
        post_limit = st.number_input("Number of Posts per Subreddit (per sorting method)", min_value=1, max_value=10000, value=10)
    else:
        post_limit = None

    # Option to collect comments.
    collect_comments = st.checkbox('Collect Comments', value=False)
    comment_method = None
    comment_limit = None
    comment_min = None
    comment_max = None

    if collect_comments:
        comment_method = st.radio("Select Comment Retrieval Method", options=["Limit", "Range", "Maximum"], index=0)
        if comment_method == "Limit":
            comment_limit = st.number_input("Number of Comments per Post", min_value=1, max_value=10000, value=10)
        elif comment_method == "Range":
            comment_min = st.number_input("Minimum Comment Index (1-based)", min_value=1, max_value=10000, value=1)
            comment_max = st.number_input("Maximum Comment Index (1-based)", min_value=1, max_value=10000, value=10)
            if comment_max < comment_min:
                st.error("Maximum Comment Index must be greater than or equal to Minimum Comment Index.")
                return

    sleep_time = st.number_input('Sleep Time (seconds) between API calls', min_value=0.0, value=0.5, step=0.1, format="%.1f")

    # --- Data Collection Execution ---
    if st.button('Start/Resume Data Collection'):
        if client_id and client_secret and username and password:
            if subreddits_input:
                subreddits = [s.strip() for s in subreddits_input.split(',') if s.strip()]
                if not subreddits:
                    st.error("Please enter at least one valid subreddit name.")
                    return
                reddit = initialize_reddit(client_id, client_secret, username, password)
                if reddit:
                    with st.spinner('Collecting data...'):
                        data = collect_reddit_data(
                            reddit,
                            subreddits,
                            sorting_methods,
                            post_limit,
                            collect_comments,
                            sleep_time,
                            comment_method,
                            comment_limit,
                            comment_min,
                            comment_max
                        )
                        if data:
                            columns = [
                                "Subreddit", "Post ID", "Post Title", "Post Author", "Post Score", "Post Num Comments",
                                "Post Upvote Ratio", "Post URL", "Post Timestamp", "Sorting Method",
                                "Comment Author", "Comment Score", "Comment Body", "Comment Timestamp"
                            ]
                            df = pd.DataFrame(data, columns=columns)
                            st.write(f"Data collected: **{df.shape[0]} records**")
                            st.write(df.head())
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(label='Download CSV', data=csv, file_name='reddit_data.csv')
            else:
                st.error("Please enter at least one subreddit name.")
        else:
            st.error("Please enter all Reddit API credentials.")

    # --- Option to Clear Collected Data ---
    if st.button("Clear Collected Data"):
        st.session_state["collected_data"] = []
        st.success("Collected data has been cleared.")

    add_footer()

if __name__ == "__main__":
    main()
