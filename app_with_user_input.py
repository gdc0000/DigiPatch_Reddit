import streamlit as st
import datetime
import pandas as pd
import praw
from praw.exceptions import APIException
from tqdm import tqdm

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

# Function to collect Reddit data
def collect_reddit_data(reddit, subreddit_name, sorting_methods, limit):
    try:
        subreddit = reddit.subreddit(subreddit_name)
        all_data = []

        for sorting_method in sorting_methods:
            st.write(f"Collecting posts sorted by {sorting_method}...")
            posts = getattr(subreddit, sorting_method)(limit=limit)

            for post in tqdm(posts, desc=f"Collecting posts ({sorting_method})"):
                post_data = [
                    post.title, str(post.author), post.score, post.num_comments,
                    post.upvote_ratio, post.url, datetime.datetime.utcfromtimestamp(post.created_utc),
                    sorting_method
                ]
                all_data.append(post_data)

        return all_data
    except APIException as e:
        st.error(f"Reddit API Exception: {e}")
        return []
    except Exception as e:
        st.error(f"Error collecting data: {e}")
        return []

# Streamlit app
def main():
    # Display the logo at the top
    st.image("DigiPatchLogo.png", width=700)  # Replace "logo.png" with the actual path to the logo file
    st.title("WP4 DigiPatch: Reddit post data collection")
    st.markdown("This tool allows users to collect Reddit post data for analysis.")

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

    if st.button('Collect Data'):
        if client_id and client_secret and username and password:
            if subreddit_name:
                reddit = initialize_reddit(client_id, client_secret, username, password)
                if reddit:
                    with st.spinner('Collecting data...'):
                        data = collect_reddit_data(reddit, subreddit_name, sorting_methods, limit)
                        if data:
                            df = pd.DataFrame(data, columns=[
                                'Title', 'Author', 'Score', 'Comments', 'Upvote Ratio', 'URL', 'Timestamp', 'Sorting Method'
                            ])

                            st.write(f"Data collected: {df.shape[0]} posts")
                            st.write(df.head())

                            # Save to CSV
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(label='Download CSV', data=csv, file_name=f'{subreddit_name}_posts.csv')

            else:
                st.error('Please enter a subreddit name')
        else:
            st.error('Please enter all Reddit API credentials')

if __name__ == "__main__":
    main()
