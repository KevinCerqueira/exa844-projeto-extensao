import re
import urllib
import os
from collections import OrderedDict
import gdown
import log
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from datetime import datetime
from collections import OrderedDict
import json

class OCR:
    
    def __init__(self):
        """
        Inicializa o objeto JSON com valores padrão.
        """
        self.json = OrderedDict({
            "numero": "",
            "ano": 0,
            "data": "",
            "reitor": "",
            "cabecalho": "",
            "texto": "",
            "link": ""
        })

    def main(self, link):
        """
        Executa a extração OCR no link especificado.
        """

        # Registra o link recebido
        log.debug("OCR:main - ", f"Link recebido: {link}")

        # Baixa o arquivo e extrai o texto
        file_name = self.download_file(link)
        text = self.extract_text(file_name)

        # Adiciona o texto extraído e o link ao dicionário de metadados
        self.json["link"] = link

        # Extrai metadados adicionais do texto
        self.extract_text_resolucao(text)
        self.extract_resolucao(text)
        self.extract_date(text)
        self.extract_reitor(text)
        self.extract_cabecalho(text)

        # Registra que a extração está concluída
        log.info("OCR:main - ", "Extração concluída, json final: " + json.dumps(self.json, sort_keys=False))
        os.remove(file_name)

        # Retorna o dicionário de metadados
        return self.json


    def extract_text(self, file_name:str) -> str:
        """
        Extrai todo o texto do PDF
        """
        text = ""
        with open(file_name, 'rb') as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
        
        for i in range(num_pages):
            images = convert_from_path(file_name, first_page=i+1, last_page=i+1)
            for image in images:
                text += pytesseract.image_to_string(image)
        return text

    def extract_resolucao(self, text:str):
        """
        Extrai o número da resolução e o ano
        """
        result = re.search(r'RESOLU[GC]AO CONSEPE\s*N[º°]\s*(\d{2,3}\s*/\s*\d{2,4})', text)
        
        try:
            if result:
                self.json["numero"] = result.group(1).replace(" ", "")
                self.json["ano"] = self.json["numero"].split("/")[1]
                if(len(self.json["ano"]) == 2):
                    if(self.json["ano"][0] == "9"):
                        self.json["ano"] = "19" + self.json["ano"]
                    elif(self.json["ano"][0] == "1" or self.json["ano"][0] == "2"):
                        self.json["ano"] = "20" + self.json["ano"]
                self.json["ano"] = int(self.json["ano"])
            if(self.json["numero"] == ""):
                result = re.search(r'RESOLU[GC]AO CONSEPE\s*(\d{2,3}\s*/\s*\d{2,4})', text)
                if result:
                    self.json["numero"] = result.group(1).replace(" ", "")                        
                if(self.json["numero"] == ""):
                    raise Exception(f"SecondTry: Unable to extract numero and ano from: *** {text} ***")
        except Exception as e:
            log.error("OCR:extract_resolucao - ", str({e}))
    def extract_date(self, text:str):
        """
        Extrai a data de quando assinado a resolução
        """
        meses = {'janeiro': 'January', 'fevereiro': 'February', 'março': 'March',
            'marco': 'March', 'abril': 'April', 'maio': 'May', 'junho': 'June', 
            'julho': 'July', 'agosto': 'August', 'setembro': 'September', 
            'outubro': 'October', 'novembro': 'November', 'dezembro': 'December'}
        
        result = re.findall(r'(\d{1,2} de [a-zç]+ de \d{4})', text, re.IGNORECASE)
        
        if result:
            self.json["data"] = result[0]
            if(self.json["data"][-4:] != self.json["ano"] and self.json["ano"] != 0):
                for i, group in enumerate(result, start=1):
                    if(group[-4:] == str(self.json["ano"])):
                        self.json["data"] = group
                        break
            if(self.json["data"] != ""):
                dia, mes, ano = self.json["data"].split(' de ')
                mes = meses[mes.lower()]
                data_obj = datetime.strptime(f'{dia} {mes} {ano}', '%d %B %Y')
                data_str = data_obj.strftime('%d/%m/%Y')
                self.json["data"] = data_str
            
            if(self.json["ano"] == 0 and self.json["data"] != ""):
                self.json["ano"] = int(self.json["data"].split("/")[2])
        else:
            log.error("OCR:extract_date - ", f"Unable to extract data from: *** {text} ***")
        
    def extract_reitor(self, text:str):
        """
        Extrai o nome do reitor
        """
        resultado = re.search(r'\n(.*)\n+(?:Reitor|Reitora|Reifor)\s', text, re.IGNORECASE)
        if resultado:
            self.json["reitor"] = resultado.group(1).strip().replace("16", "Jo")
            if("PAIM" in self.json["reitor"]):
                self.json["reitor"] = "ANACI BISPO PAIM"
            elif("oavista" in self.json["reitor"] or "Cunha" in self.json["reitor"]):
                self.json["reitor"] = "José Onofre Gurjão Boavista da Cunha"
            elif("MELLO" in self.json["reitor"] or "Cunha" in self.json["reitor"]):
                self.json["reitor"] = "Josué da Silva Mello"
        if(self.json["reitor"] == ""):
            self.json["reitor"] = "Não identificado"
            log.error("OCR:extract_reitor - ", f"Unable to extract reitor from: *** {text} ***")
    
    def extract_cabecalho(self, text:str):
        """
        Extrai somente o cabecalho da resolução
        """
        resultado = re.search(r'RESOLU[GC]AO CONSEPE.*?\n+(.*?)\n+RESOLVE', text, re.IGNORECASE | re.DOTALL)
        if resultado:
            self.json["cabecalho"] = resultado.group(1).strip()
        else:
            log.error("OCR:extract_cabecalho - ", f"Unable to extract cabecalho from: *** {text} ***")
            
    def extract_text_resolucao(self, text:str):
        """
        Extrai todo o texto do PDF
        """
        split_text = re.split(r'RESOLVE', text, flags=re.IGNORECASE)

        if len(split_text) > 1:
            # Retorna tudo após o primeiro "RESOLUCAO" ou "RESOLUGAO", que corresponde ao segundo item da lista
            self.json["texto"] = split_text[1].strip()
        else:
            self.json["texto"] = text
        
    def download_file(self, link_drive:str) -> str:
        """
        Baixa o arquivo PDF com base no link do drive
        """
        link = link_drive
        if("/file/d/" in link_drive):
            file_id = link_drive.split("/file/d/")[1].split("/")[0]
            link = "https://drive.google.com/uc?export=download&id=" + file_id
            
        if not os.path.exists('tmp'):
            os.makedirs('tmp')

        file_name = f'/tmp/{file_id}.pdf'
        
        log.debug("OCR:download_file - ", f"Downloading file: {f'{file_id}.pdf'} from {link}")
        
        gdown.download(link, file_name, quiet=False)
        return file_name
