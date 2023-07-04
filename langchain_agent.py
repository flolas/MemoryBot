from pandasai import PandasAI
from langchain.agents import Tool
from langchain.agents import load_tools
from langchain.agents import AgentType
from langchain.memory import ConversationBufferMemory
from langchain import OpenAI
from prompt import PREFIX
from langchain.utilities import SerpAPIWrapper
from langchain.agents import initialize_agent

import pandasai.llm.openai as pandasai_oa

def get_langchain_agent(df, open_api_key):

    llm = OpenAI(temperature=0.01,
                openai_api_key=open_api_key, 
                model_name='gpt-3.5-turbo', 
                verbose=True) 

    
    tools = load_tools(
        ["llm-math"], 
        llm=llm
    )

    data_analyst_agent = PandasAI(pandasai_oa.OpenAI(api_token=open_api_key))
    data_analyst_agent_tool = Tool(
        name='AskToDataAnalystAgent',
        func=lambda x: data_analyst_agent.run(df, prompt),
        description='''Instructions
        - Useful for asking questions about the financial data of the person. The data analyst 
          has access to a pandas dataframe for analysis with the following columns:
            - year_month (index)
            - ingress
            - egress
            - spendings
            - spendings_median
            - savings_median
            - income_median
            - mortgage_median
            - credit_card_usage_median
        - Use as following AskToDataAnalystAgent($QUESTION)
        '''
    )
    tools.append(data_analyst_agent_tool)


    memory = ConversationBufferMemory(memory_key="chat_history")

    agent_chain = initialize_agent(tools,
                                   llm,
                                   agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
                                   verbose=True,
                                   memory=memory,
                                   agent_kwargs={
                                        'prefix': PREFIX,
                                    }
                                   )

    return conversational_agent