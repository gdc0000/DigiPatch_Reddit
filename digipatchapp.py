import streamlit as st
import datetime
import pandas as pd
import praw
from praw.exceptions import APIException
from tqdm import tqdm

def add_footer():
    st.markdown("---")
    st.markdown("### **Gabriele Di Cicco, PhD in Social Psychology**")
    st.markdown("""
    [GitHub](https://github.com/gdc0000) | 
    [ORCID](https://orcid.org/0000-0002-1439-5790) | 
    [LinkedIn](https://www.linkedin.com/in/gabriele-di-cicco-124067b0/)
    """)

# Function to initialize Reddit instance
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

# Function to collect Reddit posts and (optionally) comments
def collect_reddit_data(reddit, subreddit_name, sorting_methods, limit, collect_comments=False):
    try:
        subreddit = reddit.subreddit(subreddit_name)
        all_posts = []
        all_comments = []

        for sorting_method in sorting_methods:
            st.write(f"Collecting posts sorted by **{sorting_method}**...")
            posts = getattr(subreddit, sorting_method)(limit=limit)

            for post in tqdm(posts, desc=f"Collecting posts ({sorting_method})"):
                # Collect post data (including post id for linking to comments)
                post_data = [
                    post.id,
                    post.title,
                    str(post.author),
                    post.score,
                    post.num_comments,
                    post.upvote_ratio,
                    post.url,
                    datetime.datetime.utcfromtimestamp(post.created_utc),
                    sorting_method
                ]
                all_posts.append(post_data)

                # If comments should be collected, get all comments for this post
                if collect_comments:
                    try:
                        post.comments.replace_more(limit=0)
                        for comment in post.comments.list():
                            comment_data = [
                                post.id,                       # ID of the post this comment belongs to
                                post.title,                    # Post title
                                str(comment.author),
                                comment.score,
                                comment.body,
                                datetime.datetime.utcfromtimestamp(comment.created_utc)
                            ]
                            all_comments.append(comment_data)
                    except Exception as e:
                        st.error(f"Error collecting comments for post {post.id}: {e}")

        return all_posts, all_comments
    except APIException as e:
        st.error(f"Reddit API Exception: {e}")
        return [], []
    except Exception as e:
        st.error(f"Error collecting data: {e}")
        return [], []

# Streamlit app
def main():
    # Display the logo at the top
    st.image("DigiPatchLogo.png", width=700)  # Replace with the actual path to your logo file
    st.title("WP4 DigiPatch: Reddit Data Collection")
    st.markdown("This tool allows users to collect Reddit post data for analysis.")
    st.markdown("https://digipatch.eu/")

    # User credentials input
    st.header("Reddit API Credentials")
    client_id = st.text_input("Client ID")
    client_secret = st.text_input("Client Secret")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    # User input for subreddit and data collection parameters
    st.header("Subreddit and Data Parameters")
    subreddit_name = st.text_input('Subreddit Name', '')
    sorting_methods = st.multiselect(
        'Sorting Methods',
        ['hot', 'new', 'top', 'controversial', 'rising'],
        default=['hot']
    )
    limit = st.number_input('Number of Posts', min_value=1, max_value=1000, value=10)
    
    # Checkbox to decide whether to collect comments as well
    collect_comments = st.checkbox('Collect Comments', value=False)

    if st.button('Collect Data'):
        if client_id and client_secret and username and password:
            if subreddit_name:
                reddit = initialize_reddit(client_id, client_secret, username, password)
                if reddit:
                    with st.spinner('Collecting data...'):
                        posts, comments = collect_reddit_data(reddit, subreddit_name, sorting_methods, limit, collect_comments)
                        
                        if posts:
                            df_posts = pd.DataFrame(posts, columns=[
                                'Post ID', 'Title', 'Author', 'Score', 'Comments', 'Upvote Ratio', 'URL', 'Timestamp', 'Sorting Method'
                            ])
                            st.write(f"Data collected: **{df_posts.shape[0]} posts**")
                            st.write(df_posts.head())

                            csv_posts = df_posts.to_csv(index=False).encode('utf-8')
                            st.download_button(label='Download Posts CSV', data=csv_posts, file_name=f'{subreddit_name}_posts.csv')

                        if collect_comments:
                            if comments:
                                df_comments = pd.DataFrame(comments, columns=[
                                    'Post ID', 'Post Title', 'Comment Author', 'Comment Score', 'Comment Body', 'Comment Timestamp'
                                ])
                                st.write(f"Data collected: **{df_comments.shape[0]} comments**")
                                st.write(df_comments.head())

                                csv_comments = df_comments.to_csv(index=False).encode('utf-8')
                                st.download_button(label='Download Comments CSV', data=csv_comments, file_name=f'{subreddit_name}_comments.csv')
                            else:
                                st.warning("No comments were found for the collected posts.")
            else:
                st.error('Please enter a subreddit name')
        else:
            st.error('Please enter all Reddit API credentials')
    
    # Footer Section
    add_footer()

if __name__ == "__main__":
    main()
