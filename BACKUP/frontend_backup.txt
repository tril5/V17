
import streamlit as st

# Import backend functions
from backend import calculate_results

# Page configuration
st.set_page_config(
    page_title="Data Analysis Dashboard",
    layout="wide"
)

# Dashboard heading
st.title("My Data Analysis Dashboard")

st.write("CSV Data Calculation Results")

# Retrieve calculations from backend
df, total_quantity, total_value, average_price = calculate_results()

# Display original and calculated data
st.subheader("Imported Dataset")

st.dataframe(df, use_container_width=True)

# Display calculated results
st.subheader("Calculation Summary")


col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Quantity", total_quantity)

with col2:
    st.metric("Total Value", total_value)

with col3:
    st.metric("Average Price", round(average_price, 2))

# Display a chart
st.subheader("Product Value Analysis")

st.bar_chart(
    df.set_index("Product")["Total Value"]
)
