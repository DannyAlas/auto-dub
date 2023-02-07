from auth import DEEPL_AUTH
from deepl.translator import TextResult
from typing import List

class DEEPL_API(DEEPL_AUTH):
    """The base class for the DeepL API

    Methods
    -------
    translate_text(text: list, target_lang: str, tag_handling: str = "html")
        translates a list of strings to a target language
    """

    def __init__(self):
        super().__init__()
    
    def translate_text(self, text: list, target_lang: str, formality: str = "default", tag_handling: str = "html") -> TextResult | List[TextResult]:
        """ Translates a list of strings to a target language 

        Parameters
        ----------
        text : list
            A list of strings to be translated
        target_lang : str
            The target language to translate to
        tag_handling : str, optional
            The tag handling to use, by default "html"
        
        Returns
        -------
        list
            A list of translated strings
        """

        response = self.deepl_auth_object.translate_text(
            text, target_lang=target_lang, formality=formality, tag_handling=tag_handling
        )

        return response
