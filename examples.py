"""
Example Tasks - Ready-to-run examples for different use cases
"""
from agent import BrowserAgent
import time


def example_1_google_search():
    """Simple Google search"""
    print("\n" + "="*60)
    print("Example 1: Google Search")
    print("="*60)
    
    agent = BrowserAgent(headless=False)
    agent.start()
    
    try:
        agent.run(
            "Search for 'playwright python tutorial' and tell me the first result's title",
            initial_url="https://google.com"
        )
    finally:
        time.sleep(2)
        agent.close()


def example_2_hacker_news():
    """Extract Hacker News top stories"""
    print("\n" + "="*60)
    print("Example 2: Hacker News Top Stories")
    print("="*60)
    
    agent = BrowserAgent(headless=False)
    agent.start()
    
    try:
        agent.run(
            "List the titles of the top 5 stories on Hacker News",
            initial_url="https://news.ycombinator.com"
        )
    finally:
        time.sleep(2)
        agent.close()


def example_3_wikipedia_search():
    """Wikipedia article navigation"""
    print("\n" + "="*60)
    print("Example 3: Wikipedia Article")
    print("="*60)
    
    agent = BrowserAgent(headless=False)
    agent.start()
    
    try:
        agent.run(
            "Go to Wikipedia, search for 'Artificial Intelligence', and summarize the first paragraph",
            initial_url="https://wikipedia.org"
        )
    finally:
        time.sleep(2)
        agent.close()


def example_4_github_exploration():
    """GitHub repository exploration"""
    print("\n" + "="*60)
    print("Example 4: GitHub Repository")
    print("="*60)
    
    agent = BrowserAgent(headless=False)
    agent.start()
    
    try:
        agent.run(
            "Go to the GitHub repository 'microsoft/playwright' and tell me how many stars it has",
            initial_url="https://github.com/microsoft/playwright"
        )
    finally:
        time.sleep(2)
        agent.close()


def example_5_multi_step():
    """Complex multi-step task"""
    print("\n" + "="*60)
    print("Example 5: Multi-Step Task")
    print("="*60)
    
    agent = BrowserAgent(headless=False)
    agent.start()
    
    try:
        agent.run(
            """
            Go to Google, search for 'best programming languages 2024',
            click on the first result, scroll down to see more content,
            and summarize the top 3 programming languages mentioned.
            """,
            initial_url="https://google.com"
        )
    finally:
        time.sleep(2)
        agent.close()


def example_6_form_demo():
    """Form interaction demo (using a test site)"""
    print("\n" + "="*60)
    print("Example 6: Form Interaction")
    print("="*60)
    
    agent = BrowserAgent(headless=False)
    agent.start()
    
    try:
        # Using a public test form
        agent.run(
            """
            On this form testing site, find the name field and type 'John Doe',
            find the email field and type 'john@example.com',
            then tell me if you can see a submit button.
            """,
            initial_url="https://www.htmlquick.com/reference/tags/form.html"
        )
    finally:
        time.sleep(2)
        agent.close()


def example_7_reddit():
    """Reddit browsing"""
    print("\n" + "="*60)
    print("Example 7: Reddit Top Posts")
    print("="*60)
    
    agent = BrowserAgent(headless=False)
    agent.start()
    
    try:
        agent.run(
            "Go to reddit.com/r/programming and tell me the titles of the top 3 hot posts",
            initial_url="https://old.reddit.com/r/programming"
        )
    finally:
        time.sleep(2)
        agent.close()


def example_8_stackoverflow():
    """StackOverflow search"""
    print("\n" + "="*60)
    print("Example 8: StackOverflow Search")
    print("="*60)
    
    agent = BrowserAgent(headless=False)
    agent.start()
    
    try:
        agent.run(
            """
            Search StackOverflow for 'python async await',
            click on the first question,
            and tell me how many upvotes it has.
            """,
            initial_url="https://stackoverflow.com"
        )
    finally:
        time.sleep(2)
        agent.close()


def main():
    """Run examples - uncomment the one you want"""
    
    # Uncomment ONE example to run:
    
    example_1_google_search()
    # example_2_hacker_news()
    # example_3_wikipedia_search()
    # example_4_github_exploration()
    # example_5_multi_step()
    # example_6_form_demo()
    # example_7_reddit()
    # example_8_stackoverflow()


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║        Browser Automation Agent - Examples             ║
    ╚════════════════════════════════════════════════════════╝
    
    Edit this file to uncomment the example you want to run.
    Each example demonstrates different capabilities.
    
    Starting in 2 seconds...
    """)
    time.sleep(2)
    main()
