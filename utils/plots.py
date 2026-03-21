import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

def barplot_counts(df: pd.DataFrame, col: str, title: str):
    counts = df[col].value_counts(dropna=False).reset_index()
    counts.columns = [col, 'n']
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=counts, x='n', y=col, ax=ax, color="#2B8CBE")
    ax.set_title(title)
    ax.set_xlabel("Count")
    ax.set_ylabel(col)
    fig.tight_layout()
    return fig