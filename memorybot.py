"""
This is a Python script that serves as a frontend for a conversational AI model built with the `langchain` and `llms` libraries.
The code creates a web application using Streamlit, a Python library for building interactive web apps.
# Author: Avratanu Biswas
# Date: March 11, 2023
"""

# Import necessary libraries
import streamlit as st
import html
import time
import requests
import numpy as np
import plotly.graph_objects as px
import pandasai.llm.openai as pandasai_oa
from streamlit_modal import Modal
import st_bridge as stb
from langchain.callbacks import StreamlitCallbackHandler

import streamlit.components.v1 as components
import uuid

import openai
openai.organization = st.secrets["OPENAI_ORGANIZATION"]

from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationEntityMemory
from langchain.chains.conversation.prompt import ENTITY_MEMORY_CONVERSATION_TEMPLATE
from langchain.llms import OpenAI
import pandas as pd
from pandasai import PandasAI

from process_movements import get_analytical_dataframes

from langchain_agent import get_langchain_agent

# Set Streamlit page configuration
st.set_page_config(page_title='Radiografía Financiera', layout='wide')

# Initialize session states
if "generated" not in st.session_state:
    st.session_state["generated"] = []
if "past" not in st.session_state:
    st.session_state["past"] = []
if "input" not in st.session_state:
    st.session_state["input"] = ""
if "stored_session" not in st.session_state:
    st.session_state["stored_session"] = []
if "fintoc_links" not in st.session_state:
    st.session_state["fintoc_links"] = {}
if "langchain_init" not in st.session_state:
    st.session_state["langchain_init"] = None
if "fintoc_data" not in st.session_state:
    st.session_state["fintoc_data"] = None

# Define function to get user input
def get_text():
    """
    Get the user input text.

    Returns:
        (str): The text entered by the user
    """
    input_text = st.text_input("You: ", st.session_state["input"], key="input",
                            placeholder="Your AI assistant here! Ask me anything ...", 
                            label_visibility='hidden')
    return input_text

# Define function to start a new chat
def new_chat():
    """
    Clears session state and starts a new chat.
    """
    save = []
    for i in range(len(st.session_state['generated'])-1, -1, -1):
        save.append("User:" + st.session_state["past"][i])
        save.append("Bot:" + st.session_state["generated"][i])        
    st.session_state["stored_session"].append(save)
    st.session_state["generated"] = []
    st.session_state["past"] = []
    st.session_state["input"] = "" 

st.title("Radiografia Financiera")
st.subheader("Conoce cómo están tus finanzas!")

# Carga Widget Fintoc
modal = Modal("", "fintoc-modal")

agree = st.checkbox('Doy mi consentimiento para el tratamiento de mis datos en radiografiafinanciera.cl (esta pagina), proveedores Fintoc y OpenAI con la finalidad de que se me entregue una asesoría y diagnotisco de mis finanzas.')
st.caption('Los datos serán eliminados una vez que cierres el explorador, si quieres volver a utilizar la herramienta debes ingresar nuevamente tus datos bancarios.')

data = stb.bridge("fintoc-bridge")

open_modal = st.button("Conectar mis cuentas bancarias 🔌 🏦", disabled = not agree)

if open_modal:
    modal.open()
    
if modal.is_open():
    with modal.container():
        url = "https://api.fintoc.com/v1/link_intents"

        payload = {
            "product": "movements",
            "country": "cl",
            "holder_type": "individual"
        }
        headers = {
            "accept": "application/json",
            "Authorization": st.secrets["FINTOC_SECRET_KEY"],
            "content-type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)

        widget_token = response.json()['widget_token']
        components.html("""
                <script src="https://js.fintoc.com/v1/"></script>
                <script>
                function waitForElm(selector) {
                    return new Promise(resolve => {
                        if (document.querySelector(selector)) {
                            return resolve(document.querySelector(selector));
                        }

                        const observer = new MutationObserver(mutations => {
                            if (document.querySelector(selector)) {
                                resolve(document.querySelector(selector));
                                observer.disconnect();
                            }
                        });

                        observer.observe(document.body, {
                            childList: true,
                            subtree: true
                        });
                    });
                }
                
                window.onload = () => {
                    waitForElm('#fintoc-widget-id').then((elm) => {
                        console.log('Fintoc iframe loaded!');
                        elm.src = elm.src.replace("null", "*")
                    });
                    window.fintocWidget = Fintoc.create({
                    publicKey: '<PUBLIC_KEY>',
                    widgetToken: '<WIDGET_TOKEN>',
                    onSuccess: (link) => {
                        console.log('Success!');
                        window.top.stBridges.send('fintoc-bridge', link)
                    },
                    onExit: () => {
                        console.log('Widget closing!');
                    },
                    onEvent: (event) => {
                        console.log('An event just happened!');
                        console.log(event);
                    },
                    });
                    
                    window.fintocWidget.open()

                };
                </script>""".replace("<PUBLIC_KEY>", st.secrets["FINTOC_PUBLIC_KEY"]).replace("<WIDGET_TOKEN>", widget_token),  height = 750)

if data is not None:
    if data['id'] not in st.session_state["fintoc_links"] or len(st.session_state["fintoc_links"][data['id']]) < 4:
        st.session_state["fintoc_links"][data['id']] = {
            "exchange_token": data['exchangeToken'],
        }

        url = f"https://api.fintoc.com/v1/links/exchange?exchange_token={data['exchangeToken']}"
        headers = {
            "accept": "application/json",
            "Authorization": st.secrets["FINTOC_SECRET_KEY"],
        }
        response = requests.get(url, headers=headers).json()
        st.session_state["fintoc_links"][data['id']]['link_token'] = response['link_token']
        st.session_state["fintoc_links"][data['id']]['accounts'] = response['accounts']
        st.session_state["fintoc_links"][data['id']]['bank'] = response['institution']['name']
        st.session_state["fintoc_links"][data['id']]['holder_id'] = response['holder_id']
        data = None
        modal.close()

    #st.session_state["fintoc_links"]
st.write('---')

debug = True
st.subheader('Cuentas Conectadas')
col1, col2, col3= st.columns([2, 2 ,1])
if len(st.session_state["fintoc_links"]) > 0:
    try:
        for link_id, link in st.session_state["fintoc_links"].items():
            with col1:
                st.write(f'🏦 Banco: {link["bank"]}') 
                st.write(f'👤 Usuario: {link["holder_id"]}') 
                if debug:
                    st.write(f'🔗 Link Token: {link["link_token"]}') 
            with col2:
                for account in link['accounts']:
                    st.write(f'📋 No: {account["number"]} ({account["name"]})') 
            with col3:
                st.button('Eliminar ❌', key = link_id, type = 'secondary', on_click=lambda : st.session_state["fintoc_links"].pop(link_id), use_container_width=True)
    except Exception as e:
        st.session_state["fintoc_links"]
        raise e
else:
    st.write("No tienes ninguna cuenta conectada.")
st.write('---')

if st.session_state["fintoc_data"] is not None and st.session_state["langchain_init"] is None:
    st.session_state["langchain_init"] = get_langchain_agent(st.session_state["fintoc_data"], st.secrets["OPENAI_API_KEY"])

def retrieve_data():
    with st.chat_message("assistant"):
        st.write("Obteniendo tu información bancaria...")
        link_tokens_available = []
        for link_id, link in st.session_state["fintoc_links"].items():
            link_tokens_available.append(link["link_token"])
        if st.session_state["fintoc_data"] is not None:
            st.session_state["fintoc_data"]  = None
            st.session_state["langchain_init"] = None
            new_chat()
        st.session_state["fintoc_data"] = get_analytical_dataframes(
        fintoc_secret_key =  st.secrets["FINTOC_SECRET_KEY"],
        link_tokens = link_tokens_available,
        since="2022-01-01",
        until="2023-07-01",
        )
st.button("Terminé de agregar bancos", disabled = len(st.session_state["fintoc_links"]) == 0, on_click = retrieve_data)
if debug:
    st.write("Se calcularon los siguientes datos")
    st.session_state["fintoc_data"]
with st.container():
    prompt = st.chat_input("Preguntame algo relacionado a tu situacion financiera...")
    with st.chat_message("assistant"):
        st.write("Hola 👋!, para poder entregarte asesoría financiera, primero debes agregar cuentas")
        if st.session_state["langchain_init"] is not None:
            st.write("Muy bien! Ya terminé de obtener tu información desde tus bancos.")
            st.write("Partiré con algunos datos interesantes que encontré!")

    if prompt and st.session_state["langchain_init"] is not None:
        agent = st.session_state["langchain_init"]
        st_callback = StreamlitCallbackHandler(st.container())
        output = agent.run(prompt, callbacks=[st_callback])
        st.session_state.past.append(prompt)  
        st.session_state.generated.append(output) 

    if len(st.session_state.past) > 0:
        for idx, user_message in enumerate(st.session_state.past):
            with st.chat_message("user"):
                st.write(user_message)
            with st.chat_message("assistant"):
                try:
                    st.write(st.session_state.generated[idx])
                except:
                    pass
                #st.line_chart(np.random.randn(30, 3))