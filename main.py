import streamlit as st
import random

st.title("Number Guessing Game")

if "secret" not in st.session_state:
    st.session_state.secret = random.randint(1, 50)
    st.session_state.attempts = 0

guess = st.number_input("Guess a number (1-50)", min_value=1, max_value=50, step=1)
if st.button("Submit Guess"):
    st.session_state.attempts += 1
    if guess < st.session_state.secret:
        st.warning("Too low!")
    elif guess > st.session_state.secret:
        st.warning("Too high!")
    else:
        st.success(f"Correct! Attempts: {st.session_state.attempts}")

if st.button("New Game"):
    st.session_state.secret = random.randint(1, 50)
    st.session_state.attempts = 0
    st.info("Started a new game!")