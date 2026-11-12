
import pandas as pd

# 1. Import Excel data
def load_data():
    # Read Excel file using the second row as headings
    df = pd.read_excel("prototype_dataset1.xlsx", header=1)

    # Remove empty columns
    df = df.dropna(axis=1, how="all")

    # Remove extra spaces from column names
    df.columns = df.columns.astype(str).str.strip()

    return df


# 2. Perform calculations
def calculate_results():

    df = load_data()

    # Calculate total value
    df["Total Value"] = df["Quantity"] * df["Price"]

    # Calculate total quantity
    total_quantity = df["Quantity"].sum()

    # Calculate total value
    total_value = df["Total Value"].sum()

    # Calculate average price
    average_price = df["Price"].mean()

    return df, total_quantity, total_value, average_price
