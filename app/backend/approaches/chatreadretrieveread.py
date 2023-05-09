import openai
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from approaches.approach import Approach
from text import nonewlines

# Simple retrieve-then-read implementation, using the Cognitive Search and OpenAI APIs directly. It first retrieves
# top documents from search, then constructs a prompt with them, and then uses OpenAI to generate an completion 
# (answer) with that prompt.
class ChatReadRetrieveReadApproach(Approach):
    prompt_prefix = """<|im_start|>system
A Judy, auxilia os funcionários da empresa com suas perguntas sobre o manual do funcionário. Seja breve em suas respostas.
Responda APENAS com os fatos listados na lista de fontes abaixo. Se não houver informações suficientes abaixo, diga que não sabe. Não crie respostas que não usem as fontes abaixo. Se perguntar uma pergunta esclarecedora para o usuário ajudar, faça a pergunta.
Para informações tabulares, retorne como uma tabela HTML. Não retorne em formato markdown.
Cada fonte tem um nome seguido de dois pontos e a informação real, sempre inclua o nome da fonte para cada fato que você usar na resposta. Use colchetes para referenciar a fonte, por exemplo, [info1.txt]. Não combine fontes, liste cada fonte separadamente, por exemplo, [info1.txt][info2.pdf].
{follow_up_questions_prompt}
{injected_prompt}
Fontes:
{sources}
<|im_end|>
{chat_history}
"""

    follow_up_questions_prompt_content = """Gere três perguntas de acompanhamento muito breves que o usuário provavelmente faria a seguir sobre seu plano de saúde e manual do funcionário. 
    Use duplo sinal de menor para referenciar as perguntas, por exemplo, <<Existem exclusões para prescrições?>>. 
    Tente não repetir perguntas que já foram feitas.
    Apenas gere perguntas e não gere nenhum texto antes ou depois das perguntas, como 'Próximas Perguntas'"""

    query_prompt_template = """Abaixo está o histórico da conversa até agora e uma nova pergunta feita pelo usuário que precisa ser respondida pesquisando em uma base de conhecimento sobre planos de saúde para funcionários e o manual do funcionário.
Gere uma consulta de pesquisa com base na conversa e na nova pergunta.
Não inclua nomes de arquivos de fontes citadas e nomes de documentos, por exemplo, info.txt ou doc.pdf, nos termos da consulta de pesquisa.
Não inclua nenhum texto dentro de [] ou <<>> nos termos da consulta de pesquisa.
Se a pergunta não estiver em inglês, traduza a pergunta para o inglês antes de gerar a consulta de pesquisa.

Chat History:
{chat_history}

Question:
{question}

Search query:
"""

    def __init__(self, search_client: SearchClient, chatgpt_deployment: str, gpt_deployment: str, sourcepage_field: str, content_field: str):
        self.search_client = search_client
        self.chatgpt_deployment = chatgpt_deployment
        self.gpt_deployment = gpt_deployment
        self.sourcepage_field = sourcepage_field
        self.content_field = content_field

    def run(self, history: list[dict], overrides: dict) -> any:
        use_semantic_captions = True if overrides.get("semantic_captions") else False
        top = overrides.get("top") or 3
        exclude_category = overrides.get("exclude_category") or None
        filter = "category ne '{}'".format(exclude_category.replace("'", "''")) if exclude_category else None

        # STEP 1: Generate an optimized keyword search query based on the chat history and the last question
        prompt = self.query_prompt_template.format(chat_history=self.get_chat_history_as_text(history, include_last_turn=False), question=history[-1]["user"])
        completion = openai.Completion.create(
            engine=self.gpt_deployment, 
            prompt=prompt, 
            temperature=0.0, 
            max_tokens=32, 
            n=1, 
            stop=["\n"])
        q = completion.choices[0].text

        # STEP 2: Retrieve relevant documents from the search index with the GPT optimized query
        if overrides.get("semantic_ranker"):
            r = self.search_client.search(q, 
                                          filter=filter,
                                          query_type=QueryType.SEMANTIC, 
                                          query_language="en-us", 
                                          query_speller="lexicon", 
                                          semantic_configuration_name="default", 
                                          top=top, 
                                          query_caption="extractive|highlight-false" if use_semantic_captions else None)
        else:
            r = self.search_client.search(q, filter=filter, top=top)
        if use_semantic_captions:
            results = [doc[self.sourcepage_field] + ": " + nonewlines(" . ".join([c.text for c in doc['@search.captions']])) for doc in r]
        else:
            results = [doc[self.sourcepage_field] + ": " + nonewlines(doc[self.content_field]) for doc in r]
        content = "\n".join(results)

        follow_up_questions_prompt = self.follow_up_questions_prompt_content if overrides.get("suggest_followup_questions") else ""
        
        # Allow client to replace the entire prompt, or to inject into the exiting prompt using >>>
        prompt_override = overrides.get("prompt_template")
        if prompt_override is None:
            prompt = self.prompt_prefix.format(injected_prompt="", sources=content, chat_history=self.get_chat_history_as_text(history), follow_up_questions_prompt=follow_up_questions_prompt)
        elif prompt_override.startswith(">>>"):
            prompt = self.prompt_prefix.format(injected_prompt=prompt_override[3:] + "\n", sources=content, chat_history=self.get_chat_history_as_text(history), follow_up_questions_prompt=follow_up_questions_prompt)
        else:
            prompt = prompt_override.format(sources=content, chat_history=self.get_chat_history_as_text(history), follow_up_questions_prompt=follow_up_questions_prompt)

        # STEP 3: Generate a contextual and content specific answer using the search results and chat history
        completion = openai.Completion.create(
            engine=self.chatgpt_deployment, 
            prompt=prompt, 
            temperature=overrides.get("temperature") or 0.7, 
            max_tokens=1024, 
            n=1, 
            stop=["<|im_end|>", "<|im_start|>"])

        return {"data_points": results, "answer": completion.choices[0].text, "thoughts": f"Searched for:<br>{q}<br><br>Prompt:<br>" + prompt.replace('\n', '<br>')}
    
    def get_chat_history_as_text(self, history, include_last_turn=True, approx_max_tokens=1000) -> str:
        history_text = ""
        for h in reversed(history if include_last_turn else history[:-1]):
            history_text = """<|im_start|>user""" +"\n" + h["user"] + "\n" + """<|im_end|>""" + "\n" + """<|im_start|>assistant""" + "\n" + (h.get("bot") + """<|im_end|>""" if h.get("bot") else "") + "\n" + history_text
            if len(history_text) > approx_max_tokens*4:
                break    
        return history_text