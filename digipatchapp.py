import streamlit as st
import datetime
import pandas as pd
import praw
from praw.exceptions import APIException
from tqdm import tqdm
import time

def add_footer():
    st.markdown("---")
    st.markdown("### **Gabriele Di Cicco, PhD in Social Psychology**")
    st.markdown("""
    [GitHub](https://github.com/gdc0000) | 
    [ORCID](https://orcid.org/0000-0002-1439-5790) | 
    [LinkedIn](https://www.linkedin.com/in/gabriele-di-cicco-124067b0/)
    """)

# Function to initialize the Reddit instance.
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

# Function to collect posts and comments from multiple subreddits.
def collect_reddit_data(reddit, subreddits, sorting_methods, limit, collect_comments, sleep_time, max_comments):
    combined_data = []
    # Estimate total iterations for progress tracking:
    total_iterations = len(subreddits) * len(sorting_methods) * limit
    current_iteration = 0
    progress_bar = st.progress(0)
    
    for subreddit_name in subreddits:
        try:
            subreddit = reddit.subreddit(subreddit_name)
        except Exception as e:
            st.error(f"Error accessing subreddit {subreddit_name}: {e}")
            continue

        for sorting_method in sorting_methods:
            st.write(f"Collecting posts from **r/{subreddit_name}** sorted by **{sorting_method}**...")
            try:
                posts = getattr(subreddit, sorting_method)(limit=limit)
            except Exception as e:
                st.error(f"Error fetching posts for r/{subreddit_name} using {sorting_method}: {e}")
                continue

            for post in tqdm(posts, desc=f"r/{subreddit_name} - {sorting_method}"):
                # Post-level details.
                post_id = post.id
                post_title = post.title
                post_author = str(post.author)
                post_score = post.score
                post_num_comments = post.num_comments
                post_upvote_ratio = post.upvote_ratio
                post_url = post.url
                post_timestamp = datetime.datetime.utcfromtimestamp(post.created_utc)
                
                if collect_comments:
                    try:
                        post.comments.replace_more(limit=0)
                        # Get all comments and then limit to max_comments per post.
                        comment_list = post.comments.list()[:max_comments]
                    except Exception as e:
                        st.error(f"Error collecting comments for post {post.id} in r/{subreddit_name}: {e}")
                        comment_list = []
                    
                    # If there are comments, create one row per comment.
                    if comment_list:
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
                            combined_data.append(row)
                    else:
                        # No comments found: add one row with comment fields set to None.
                        row = [
                            subreddit_name, post_id, post_title, post_author, post_score, post_num_comments,
                            post_upvote_ratio, post_url, post_timestamp, sorting_method,
                            None, None, None, None
                        ]
                        combined_data.append(row)
                else:
                    # Not collecting comments: add one row with empty comment fields.
                    row = [
                        subreddit_name, post_id, post_title, post_author, post_score, post_num_comments,
                        post_upvote_ratio, post_url, post_timestamp, sorting_method,
                        None, None, None, None
                    ]
                    combined_data.append(row)
                
                # Update progress and sleep briefly to help mitigate API limitations.
                current_iteration += 1
                progress_bar.progress(min(current_iteration / total_iterations, 1.0))
                time.sleep(sleep_time)
                
    return combined_data

# Streamlit app
def main():
    st.image("DigiPatchLogo.png", width=700)  # Replace with your logo file path.
    st.title("WP4 DigiPatch: Reddit Data Collection")
    st.markdown("This tool collects Reddit posts and comments across multiple subreddits for analysis.")
    st.markdown("https://digipatch.eu/")

    # Reddit API credentials.
    st.header("Reddit API Credentials")
    client_id = st.text_input("Client ID")
    client_secret = st.text_input("Client Secret")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    # Data collection parameters.
    st.header("Subreddit and Data Parameters")
    subreddits_input = st.text_input('Subreddit Names (comma-separated)', '')
    sorting_methods = st.multiselect(
        'Sorting Methods',
        ['hot', 'new', 'top', 'controversial', 'rising'],
        default=['hot']
    )
    limit = st.number_input('Number of Posts per Subreddit (per sorting method)', min_value=1, max_value=1000, value=10)
    
    # Option to collect comments.
    collect_comments = st.checkbox('Collect Comments', value=False)
    max_comments = None
    if collect_comments:
        max_comments = st.number_input("Maximum Comments per Post", min_value=1, max_value=100, value=10)
    
    # Sleep time to help mitigate API rate limitations.
    sleep_time = st.number_input('Sleep Time (seconds) between API calls', min_value=0.0, value=0.5, step=0.1, format="%.1f")

    if st.button('Collect Data'):
        if client_id and client_secret and username and password:
            if subreddits_input:
                # Prepare list of subreddits.
                subreddits = [s.strip() for s in subreddits_input.split(',') if s.strip()]
                if not subreddits:
                    st.error("Please enter at least one valid subreddit name.")
                    return
                
                reddit = initialize_reddit(client_id, client_secret, username, password)
                if reddit:
                    with st.spinner('Collecting data...'):
                        # If not collecting comments, max_comments is not needed (set to 0).
                        if not collect_comments:
                            max_comments = 0
                        data = collect_reddit_data(reddit, subreddits, sorting_methods, limit, collect_comments, sleep_time, max_comments)
                        if data:
                            columns = [
                                "Subreddit", "Post ID", "Post Title", "Post Author", "Post Score", "Post Num Comments",
                                "Post Upvote Ratio", "Post URL", "Post Timestamp", "Sorting Method",
                                "Comment Author", "Comment Score", "Comment Body", "Comment Timestamp"
                            ]
                            df = pd.DataFrame(data, columns=columns)
                            
                            st.write(f"Data collected: **{df.shape[0]} records**")
                            st.write(df.head())
                            
                            # Download button for the complete CSV.
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(label='Download CSV', data=csv, file_name='reddit_data.csv')
            else:
                st.error('Please enter at least one subreddit name')
        else:
            st.error('Please enter all Reddit API credentials')
    
    add_footer()

if __name__ == "__main__":
    main()
