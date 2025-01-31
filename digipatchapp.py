import streamlit as st
import datetime
import pandas as pd
import praw
from praw.exceptions import APIException
from tqdm import tqdm
import time
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from sklearn.feature_extraction.text import CountVectorizer
import io

def add_footer():
    st.markdown("---")
    st.markdown("### **Gabriele Di Cicco, PhD in Social Psychology**")
    st.markdown("""
    [GitHub](https://github.com/gdc0000) | 
    [ORCID](https://orcid.org/0000-0002-1439-5790) | 
    [LinkedIn](https://www.linkedin.com/in/gabriele-di-cicco-124067b0/)
    """)

# Initialize Reddit instance using PRAW.
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

# Collect posts and comments across multiple subreddits.
def collect_reddit_data(reddit, subreddits, sorting_methods, post_limit, collect_comments, sleep_time, comment_limit):
    combined_data = []
    # If a fixed post limit is set, we can estimate iterations for progress tracking.
    if post_limit is not None:
        total_iterations = len(subreddits) * len(sorting_methods) * post_limit
    else:
        total_iterations = None

    progress_bar = st.progress(0) if total_iterations is not None else None
    progress_text = st.empty() if total_iterations is None else None
    current_iteration = 0

    for subreddit_name in subreddits:
        try:
            subreddit = reddit.subreddit(subreddit_name)
        except Exception as e:
            st.error(f"Error accessing subreddit {subreddit_name}: {e}")
            continue

        for sorting_method in sorting_methods:
            st.write(f"Collecting posts from **r/{subreddit_name}** sorted by **{sorting_method}**...")
            try:
                posts = getattr(subreddit, sorting_method)(limit=post_limit)
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
                        all_comments = post.comments.list()
                        # Apply comment limit if set.
                        if comment_limit is not None:
                            comment_list = all_comments[:comment_limit]
                        else:
                            comment_list = all_comments
                    except Exception as e:
                        st.error(f"Error collecting comments for post {post.id} in r/{subreddit_name}: {e}")
                        comment_list = []
                    
                    # One row per comment.
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
                        # No comments found for this post.
                        row = [
                            subreddit_name, post_id, post_title, post_author, post_score, post_num_comments,
                            post_upvote_ratio, post_url, post_timestamp, sorting_method,
                            None, None, None, None
                        ]
                        combined_data.append(row)
                else:
                    # If not collecting comments, add a single row with empty comment fields.
                    row = [
                        subreddit_name, post_id, post_title, post_author, post_score, post_num_comments,
                        post_upvote_ratio, post_url, post_timestamp, sorting_method,
                        None, None, None, None
                    ]
                    combined_data.append(row)
                
                # Update progress and sleep briefly.
                current_iteration += 1
                if progress_bar is not None:
                    progress_bar.progress(min(current_iteration / total_iterations, 1.0))
                else:
                    progress_text.text(f"Processed {current_iteration} posts...")
                time.sleep(sleep_time)
                
    return combined_data

# Generate a wordcloud image for a given text series using n-grams.
def generate_ngram_wordcloud(text_series, ngram_range=(1,3)):
    corpus = text_series.dropna().tolist()
    if not corpus:
        return None
    vectorizer = CountVectorizer(ngram_range=ngram_range, stop_words='english')
    X = vectorizer.fit_transform(corpus)
    sum_words = X.sum(axis=0)
    words_freq = {word: sum_words[0, idx] for word, idx in vectorizer.vocabulary_.items()}
    wc = WordCloud(width=800, height=400, background_color='white')
    wc.generate_from_frequencies(words_freq)
    # Return the wordcloud image array.
    return wc.to_array()

# Main Streamlit app.
def main():
    st.image("DigiPatchLogo.png", width=700)  # Replace with your logo path.
    st.title("WP4 DigiPatch: Reddit Data Collection & Exploration")
    st.markdown("This tool collects Reddit posts and comments from multiple subreddits, then offers interactive visualizations for exploratory analysis.")
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
    
    # Post limit: fixed number or maximum.
    post_limit_option = st.radio("Select Post Limit", options=["Limit", "Maximum"], index=0)
    if post_limit_option == "Limit":
        post_limit = st.number_input("Number of Posts per Subreddit (per sorting method)", min_value=1, max_value=10000, value=10)
    else:
        post_limit = None  # Collect maximum available posts.
    
    # Option to collect comments.
    collect_comments = st.checkbox('Collect Comments', value=False)
    comment_limit = None
    if collect_comments:
        comment_limit_option = st.radio("Select Comment Limit per Post", options=["Limit", "Maximum"], index=0)
        if comment_limit_option == "Limit":
            comment_limit = st.number_input("Number of Comments per Post", min_value=1, max_value=10000, value=10)
        else:
            comment_limit = None  # Collect all available comments.
    
    # Sleep time (in seconds) between API calls to help mitigate rate limits.
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
                        data = collect_reddit_data(reddit, subreddits, sorting_methods, post_limit, collect_comments, sleep_time, comment_limit)
                        if data:
                            columns = [
                                "Subreddit", "Post ID", "Post Title", "Post Author", "Post Score", "Post Num Comments",
                                "Post Upvote Ratio", "Post URL", "Post Timestamp", "Sorting Method",
                                "Comment Author", "Comment Score", "Comment Body", "Comment Timestamp"
                            ]
                            df = pd.DataFrame(data, columns=columns)
                            
                            st.write(f"Data collected: **{df.shape[0]} records**")
                            st.dataframe(df.head())

                            # Download the complete dataset.
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(label='Download Data CSV', data=csv, file_name='reddit_data.csv', mime='text/csv')

                            st.markdown("## Data Exploration & Visualization")
                            # Create tabs for exploration.
                            tab1, tab2, tab3 = st.tabs(["Wordclouds", "Trendline", "Network"])

                            with tab1:
                                st.subheader("Wordclouds")
                                # Wordcloud for Post Titles.
                                if not df["Post Title"].dropna().empty:
                                    st.markdown("### Post Titles (1- to 3-grams)")
                                    post_wc = generate_ngram_wordcloud(df["Post Title"], ngram_range=(1,3))
                                    if post_wc is not None:
                                        st.image(post_wc, use_column_width=True)
                                    else:
                                        st.write("No post text available for wordcloud.")
                                else:
                                    st.write("No post text available.")
                                # Wordcloud for Comments (if available).
                                if collect_comments and not df["Comment Body"].dropna().empty:
                                    st.markdown("### Comments (1- to 3-grams)")
                                    comment_wc = generate_ngram_wordcloud(df["Comment Body"], ngram_range=(1,3))
                                    if comment_wc is not None:
                                        st.image(comment_wc, use_column_width=True)
                                    else:
                                        st.write("No comment text available for wordcloud.")
                                elif collect_comments:
                                    st.write("No comment text available.")

                            with tab2:
                                st.subheader("Comment Trendline")
                                # Only consider rows with a valid comment timestamp.
                                if "Comment Timestamp" in df.columns:
                                    df_comments = df.dropna(subset=["Comment Timestamp"]).copy()
                                    if not df_comments.empty:
                                        # Create a date column.
                                        df_comments["Comment Date"] = df_comments["Comment Timestamp"].dt.date
                                        trend = df_comments.groupby("Comment Date").size().reset_index(name="Count")
                                        st.line_chart(trend.rename(columns={"Comment Date": "index"}).set_index("index"))
                                    else:
                                        st.write("No comment timestamp data available.")
                                else:
                                    st.write("Comment timestamp data not available.")

                            with tab3:
                                st.subheader("Author Interaction Network")
                                # Build a weighted edge list between post authors and comment authors.
                                if "Post Author" in df.columns and "Comment Author" in df.columns:
                                    df_network = df.dropna(subset=["Comment Author"]).copy()
                                    # Filter out any non-valid author names.
                                    df_network = df_network[(df_network["Post Author"].notnull()) & (df_network["Comment Author"].notnull())]
                                    if not df_network.empty:
                                        edge_list = df_network.groupby(["Post Author", "Comment Author"]).size().reset_index(name="Weight")
                                        st.write("Weighted Edge List (Post Author → Comment Author):")
                                        st.dataframe(edge_list)
                                        csv_network = edge_list.to_csv(index=False).encode('utf-8')
                                        st.download_button(label='Download Gephi Network CSV', data=csv_network, file_name='gephi_network.csv', mime='text/csv')
                                    else:
                                        st.write("No network data available.")
                                else:
                                    st.write("Network data not available.")

                        else:
                            st.error("No data was collected.")
            else:
                st.error("Please enter at least one subreddit name")
        else:
            st.error("Please enter all Reddit API credentials")
    
    add_footer()

if __name__ == "__main__":
    main()
