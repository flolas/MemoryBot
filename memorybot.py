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

from streamlit_modal import Modal
import st_bridge as stb

import streamlit.components.v1 as components
import uuid

from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationEntityMemory
from langchain.chains.conversation.prompt import ENTITY_MEMORY_CONVERSATION_TEMPLATE
from langchain.llms import OpenAI

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
    st.session_state.entity_memory.entity_store = {}
    st.session_state.entity_memory.buffer.clear()

# Set up sidebar with various options
with st.sidebar.expander("🛠️ ", expanded=False):
    # Option to preview memory store
    if st.checkbox("Preview memory store"):
        with st.expander("Memory-Store", expanded=False):
            st.session_state.entity_memory.store
    # Option to preview memory buffer
    if st.checkbox("Preview memory buffer"):
        with st.expander("Bufffer-Store", expanded=False):
            st.session_state.entity_memory.buffer
    MODEL = st.selectbox(label='Model', options=['gpt-3.5-turbo','text-davinci-003','text-davinci-002','code-davinci-002'])
    K = st.number_input(' (#)Summary of prompts to consider',min_value=3,max_value=1000)
# Set up the Streamlit app layout
st.title("Radiografia Financiera")
st.subheader("Conoce cómo están tus finanzas!")


agree = st.checkbox('Doy mi consentimiento para el tratamiento de mis datos utilizando esta página y proveedor Fintoc con la finalidad de que se me entregue una asesoría y diagnotisco de mis finanzas.')
st.caption('Los datos serán eliminados una vez que cierres el explorador, si quieres volver a utilizar la herramienta debes ingresar nuevamente tus datos bancarios.')

open_modal = st.button("Conectar mis cuentas bancarias 🔌 🏦", disabled = not agree)


data = stb.bridge("fintoc-bridge")
if data:
    if data['id'] not in st.session_state["fintoc_links"]:
        st.session_state["fintoc_links"][data['id']] = {
            "exchange_token": data['exchange_token'],
            "user": data['username'],
        }

        url = f"https://api.fintoc.com/v1/links/exchange?exchange_token={data['exchange_token']}"
        headers = {
            "accept": "application/json",
            "Authorization": st.secrets["FINTOC_SECRET_KEY"],
        }
        response = requests.get(url, headers=headers).json()
        st.session_state["fintoc_links"][data['id']]['link_token'] = response['link_token']
        st.session_state["fintoc_links"][data['id']]['accounts'] = response['accounts']
        st.session_state["fintoc_links"][data['id']]['bank'] = response['institution']['name']
    st.session_state["fintoc_links"]
st.write('---')

#st.subheader('Bancos Conectados')
#col1, col2, col3= st.columns([1, 3 ,1])
#if len(st.session_state["fintoc_links"]) > 0:
#    for link_id, link in st.session_state["fintoc_links"].items():
#        with col1:
#            st.header(f'✅') 
#        with col2:
#            st.write(f'🏦 Banco: {link["bank"]}') 
#            st.write(f'👤 Usuario: {link["user"]}') 
#        with col3:
#            st.button('Eliminar ❌', type = 'secondary', on_click=lambda : st.session_state["fintoc_links"].pop(link_id), use_container_width=True)
#        st.write('---')
#else:
#    st.write("No tienes ninguna cuenta conectada.")

def retrieve_data():
    with st.spinner('Obteniendo movimientos...'):
        time.sleep(5)
    st.success('Done!')

st.button("Terminé de agregar bancos", disabled = len(st.session_state["fintoc_links"]) == 0, on_click = retrieve_data)

# Carga Widget Fintoc
modal = Modal("", "fintoc-modal")
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
                            console.log(link);
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


# Ask the user to enter their OpenAI API key
API_O = st.sidebar.text_input("API-KEY", type="password")

# Session state storage would be ideal
if API_O:
    # Create an OpenAI instance
    llm = OpenAI(temperature=0,
                openai_api_key=API_O, 
                model_name=MODEL, 
                verbose=False) 


    # Create a ConversationEntityMemory object if not already created
    if 'entity_memory' not in st.session_state:
            st.session_state.entity_memory = ConversationEntityMemory(llm=llm, k=K )
        
        # Create the ConversationChain object with the specified configuration
    Conversation = ConversationChain(
            llm=llm, 
            prompt=ENTITY_MEMORY_CONVERSATION_TEMPLATE,
            memory=st.session_state.entity_memory
        )  
else:
    st.sidebar.warning('API key required to try this app.The API key is not stored in any form.')
    # st.stop()


# Add a button to start a new chat
st.sidebar.button("New Chat", on_click = new_chat, type='primary')

# Get the user input
user_input = get_text()

# Generate the output using the ConversationChain object and the user input, and add the input/output to the session
if user_input:
    output = Conversation.run(input=user_input)  
    st.session_state.past.append(user_input)  
    st.session_state.generated.append(output)  

# Allow to download as well
download_str = []
# Display the conversation history using an expander, and allow the user to download it
with st.expander("Conversation", expanded=True):
    for i in range(len(st.session_state['generated'])-1, -1, -1):
        st.info(st.session_state["past"][i],icon="🧐")
        st.success(st.session_state["generated"][i], icon="🤖")
        download_str.append(st.session_state["past"][i])
        download_str.append(st.session_state["generated"][i])
    
    # Can throw error - requires fix
    download_str = '\n'.join(download_str)
    if download_str:
        st.download_button('Download',download_str)

# Display stored conversation sessions in the sidebar
for i, sublist in enumerate(st.session_state.stored_session):
        with st.sidebar.expander(label= f"Conversation-Session:{i}"):
            st.write(sublist)

# Allow the user to clear all stored conversation sessions
if st.session_state.stored_session:   
    if st.sidebar.checkbox("Clear-all"):
        del st.session_state.stored_session
