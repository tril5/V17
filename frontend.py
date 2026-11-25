
import streamlit as st
import pandas as pd

# --------------------------------
# PAGE CONFIGURATION
# --------------------------------

st.set_page_config(
    page_title="AI Business Dashboard",
    page_icon="📊",
    layout="wide"
)

# --------------------------------
# SAMPLE DATA (TEMPORARY)
# --------------------------------

# Replace this with backend data later
sample_data = pd.DataFrame({
    "Product": ["Product A", "Product B", "Product C"],
    "Quantity": [50, 30, 20],
    "Price": [100, 200, 150]
})

sample_data["Total Value"] = (
    sample_data["Quantity"] * sample_data["Price"]
)


# --------------------------------
# HOME PAGE
# --------------------------------

def home_page():

    st.title("EcoBuilder")
    st.write("A Project by Team 17")

    st.divider()

    st.subheader("Choose Your Dashboard")

    col1, col2 = st.columns(2)

    with col1:
        st.info("### 👤 Client Dashboard")
        st.write("Access client services, orders, and insights.")

        if st.button(
            "Open Client Dashboard",
            use_container_width=True
        ):
            st.session_state.page = "Client"
            st.rerun()

    with col2:
        st.success("### 🏪 Retailer Dashboard")
        st.write("Manage products and add inventory")

        if st.button(
            "Open Retailer Dashboard",
            use_container_width=True
        ):
            st.session_state.page = "Retailer"
            st.rerun()


# --------------------------------
# CLIENT DASHBOARD
# --------------------------------

def client_dashboard():

    st.title("👤 Client Dashboard")

    st.write("Welcome to your client portal.")

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Orders", 12)

    with col2:
        st.metric("Active Orders", 3)

    with col3:
        st.metric("Completed Orders", 9)

    st.divider()

    st.subheader("My Orders")

    orders = pd.DataFrame({
        "Order ID": ["ORD001", "ORD002", "ORD003"],
        "Product": ["Product A", "Product B", "Product C"],
        "Status": ["Delivered", "Processing", "Shipped"]
    })

    st.dataframe(
        orders,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Available Products")

    st.dataframe(
        sample_data[["Product", "Price"]],
        use_container_width=True,
        hide_index=True
    )

    st.info("More client features will be added soon.")


# --------------------------------
# RETAILER DASHBOARD
# --------------------------------

def retailer_dashboard():

    st.title("🏪 Retailer Dashboard")

    st.write("Manage your business operations.")

    st.divider()

    total_products = len(sample_data)
    total_quantity = sample_data["Quantity"].sum()
    total_value = sample_data["Total Value"].sum()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Products", total_products)

    with col2:
        st.metric("Total Stock", total_quantity)

    with col3:
        st.metric("Inventory Value", f"₹{total_value:,.2f}")

    st.divider()

    st.subheader("Inventory Overview")

    st.dataframe(
        sample_data,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Product Value Analysis")

    st.bar_chart(
        sample_data.set_index("Product")["Total Value"]
    )

    st.info("AI analytics and retailer tools coming soon.")


# --------------------------------
# NAVIGATION
# --------------------------------

if "page" not in st.session_state:
    st.session_state.page = "Home"

with st.sidebar:

    st.title("Navigation")

    if st.button("🏠 Home", use_container_width=True):
        st.session_state.page = "Home"
        st.rerun()

    if st.button("👤 Client", use_container_width=True):
        st.session_state.page = "Client"
        st.rerun()

    if st.button("🏪 Retailer", use_container_width=True):
        st.session_state.page = "Retailer"
        st.rerun()

    st.divider()
    st.caption("AI Business Platform | Prototype")


# --------------------------------
# DISPLAY SELECTED PAGE
# --------------------------------

if st.session_state.page == "Home":
    home_page()

elif st.session_state.page == "Client":
    client_dashboard()

elif st.session_state.page == "Retailer":
    retailer_dashboard()
