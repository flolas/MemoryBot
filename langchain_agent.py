from pandasai import PandasAI
from langchain.agents import Tool
from langchain.agents import load_tools
from langchain.agents import AgentType
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from prompt import PREFIX
from langchain.utilities import SerpAPIWrapper
from langchain.agents import initialize_agent

import pandasai.llm.openai as pandasai_oa

def get_langchain_agent(df, open_api_key):

    llm = ChatOpenAI(temperature=0.01,
                openai_api_key=open_api_key, 
                model_name='gpt-3.5-turbo', 
                verbose=True) 

    
    tools = load_tools(
        ["llm-math", "human"], 
        llm=llm
    )

    data_analyst_agent = PandasAI(pandasai_oa.OpenAI(api_token=open_api_key))

    def f_data_analyst_agent(prompt):
        try:
            return data_analyst_agent.run(df, prompt)
        except Exception as e:
            return f"Please try again with another question, I cant answer that because of '{e}'"
        
    data_analyst_agent_tool = Tool(
        name='AskFinanceDataQuestion',
        func=f_data_analyst_agent,
        description='''Make a question to an financial data analyst about the financial data of the user/person. For this tool you must formulate closed-ended questions encompassing all the necessary context.
        The data analyst has access to a pandas dataframe which has financial records of the person helping you with the following columns:
            - year_month (index)
            - ingress
            - egress
            - spendings
            - spendings_median
            - savings_median
            - income_median
            - mortgage_median
            - credit_card_usage_median
        '''
    )
    tools.append(data_analyst_agent_tool)

    agent_chain = initialize_agent(tools,
                                   llm,
                                   agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                                   verbose=True,
                                   memory=ConversationBufferMemory(return_messages=True, memory_key="chat_history"),
                                   handle_parsing_errors=True,
                                   max_iterations=5,
                                   agent_kwargs={
                                            prefix: PREFIX,
                                            handle_parsing_errors:True,
                                       }
                                   )

    return agent_chain