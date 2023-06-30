from fastapi import FastAPI, BackgroundTasks, File, UploadFile
import requests
import json
from fastapi.middleware.cors import CORSMiddleware
import re
from youtubesearchpython import VideosSearch
from bardapi import Bard
import pickle as pkl
import os
import boto3
from fastapi_scheduler import SchedulerAdmin
from fastapi_amis_admin.admin.site import AdminSite
from fastapi_amis_admin.admin.settings import Settings
from pydantic import BaseModel
import openai
import spacy
import shutil
from resume_parser import resumeparse

app = FastAPI()

site = AdminSite(settings=Settings(database_url_async='sqlite+aiosqlite:///amisadmin.db'))
scheduler = SchedulerAdmin.bind(site)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatGPTRequest(BaseModel):
    id_user: str
    role: str
    answer: str
    
class ParseVacanteRequest(BaseModel):
    descripcion_vacante: str

spacy.load('en_core_web_sm')

@app.post("/parse_resume")
async def parse_resume(file: UploadFile = File(...)):
    try:
        # Guardar el archivo subido en el sistema de archivos
        with open("temp_resume.pdf", "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Pasar la ruta del archivo a resume_parser
        parsed_resume = resumeparse.read_file("temp_resume.pdf")
        
        # Realizar operaciones con el archivo procesado
        # ...
        
        return parsed_resume
    
    finally:
        # Eliminar el archivo temporal después de procesarlo
        os.remove("temp_resume.pdf")
        

def save_to_local(obj, name):
    pkl.dump(obj, open('/app/pkl-data/'+str(name)+'.pkl', 'wb'))

def save_to_s3(obj, name):
    print('SUBIENDO {} a s3'.format(name))
    os.environ['AWS_ACCESS_KEY_ID'] = 'AKIAT36HIHLLWYBJ4VK6'
    os.environ['AWS_SECRET_ACCESS_KEY'] = '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'
    s3 = boto3.client('s3')
    bucket = 'profile-matching-coally'  # Reemplaza con el nombre de tu bucket en S3
    key = str(name)+'.pkl'  # Reemplaza con la ruta y nombre de archivo en S3
    s3.put_object(Body=pkl.dumps(obj), Bucket=bucket, Key=key)
    print('SUBIDO {} a s3'.format(name))

def load_from_local(name):
    return pkl.load(open('/app/pkl-data/'+str(name)+'.pkl', 'rb'))

def download_from_s3(name, path):
    print('DESCARGANDO '+name +' DE S3')
    s3 = boto3.client('s3',
                  aws_access_key_id='AKIAT36HIHLLWYBJ4VK6',
                  aws_secret_access_key='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')

    # Descarga el archivo PKL de S3 y guárdalo localmente
    nombre_archivo_local = str(path)+str(name)+'.pkl'
    s3.download_file('profile-matching-coally', str(name)+'.pkl', nombre_archivo_local)
    print('TERMINE DE DESCARGAR '+name +' DE S3')

@app.post("/parsear_vacante")
def parse_opportunity(request: ParseVacanteRequest):

    vacante = request.descripcion_vacante

    vacante_ejemplo = """Técnicos/Tecnólogos en electricidad para varias ciudades en el Valle (Yumbo, Palmira):
    Apoyo de sostenimiento: 1.160.000
    Fecha estimada de contratación: inmediata
    • Apoyo en las inspecciones de rutina de los equipos electrónicos de la planta
    • Apoyo en la elaboración de informes de gestión de mantenimiento
    • Apoyo en la ejecución de las actividades de mantenimiento de los equipos"""

    openai.api_key = "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"
    completion = openai.ChatCompletion.create(
    model = "gpt-3.5-turbo",
    max_tokens = 2000,
    messages = [
        {"role": "system", "content": "Eres un experto en recursos humanos."},
        {"role": "user", "content": "Extraeme la siguiente información de la vacante que te doy: Titulo, Ciudad, Habilidades blandas, Habilidades, Técnicas, Responsabilidades, Modalidad (remoto o presencial), Salario, Carrera, Tipo de contrato (Término indefinido, proyecto, prestación de servicios o full time, etc). Si no encuentras alguna pon 'NA'. La vacante es la siguiente: "+vacante_ejemplo},
        {"role": "assistant", "content": """Nombre de la vacante: Técnicos/Tecnólogos en electricidad
    Empresa: NA
    Ciudad: Yumbo, Palmira (varias ciudades en el Valle)
    Departamento: NA
    Habilidades técnicas: Inspecciones de rutina de equipos electrónicos, elaboración de informes de gestión de mantenimiento, ejecución de actividades de mantenimiento de equipos
    Habilidades blandas: NA
    Salario: 1.160.000
    Responsabilidades : Apoyo en las inspecciones de rutina de los equipos electrónicos de la planta, apoyo en la elaboración de informes de gestión de mantenimiento, apoyo en la ejecución de las actividades de mantenimiento de los equipos
    Modalidad: NA
    Carrera universitaria: Tecnología en electricidad
    Tipo de contrato: NA"""},
        {"role": "user", "content": "Extraeme la siguiente información de la vacante que te doy: Titulo, Ciudad, Habilidades blandas, Habilidades, Técnicas, Responsabilidades, Modalidad (remoto o presencial), Salario, Carrera, Tipo de contrato (Término indefinido, proyecto, prestación de servicios o full time, etc). Si no encuentras alguna pon 'NA'. La vacante es la siguiente: "+vacante}
    ]
    )

    string = str(completion.choices[0].message['content'])
    return string




@app.post("/save_chatgpt_query")
async def save_chatgpt_query(request: ChatGPTRequest, background_tasks: BackgroundTasks):
    
    id_user = request.id_user
    role = request.role
    answer = request.answer

    tries = 0
    while tries < 5:
        try:
            download_from_s3('chatgpt_responses','/app/pkl-data/')
            chatgpt_responses = load_from_local('chatgpt_responses')
            temp_dict = {}
            temp_dict['role']=role
            temp_dict['response']=answer
            chatgpt_responses[id_user] = temp_dict
            save_to_local(chatgpt_responses, 'chatgpt_responses')
            save_to_s3(chatgpt_responses, 'chatgpt_responses')
            break
        except Exception as e:
            print(e)
            tries += 1
            continue

    # chatgpt_responses = {}
    # temp_dict = {}
    # temp_dict['role']=role
    # temp_dict['response']=answer
    # chatgpt_responses[id_user] = temp_dict
    # save_to_local(chatgpt_responses, 'chatgpt_responses')
    # save_to_s3(chatgpt_responses, 'chatgpt_responses')

    background_tasks.add_task(nueva_ruta_educativa, role, id_user)

    return {"message": "respuesta agregada correctamente"}

def nueva_ruta_educativa(role: str, id_user: str):
    tries1 = 0
    while tries1 < 5:
        try:
            role = role.replace('_', ' ')

            carreer = role

            openai.api_key = "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"

            completion = openai.ChatCompletion.create(
            model = "gpt-3.5-turbo",
            max_tokens = 2000,
            messages = [
                {"role": "system", "content": "You are a curriculum designer."},
                {"role": "user", "content": "Please design for me a curriculum for being a data analyst. Provide it in a json format"},
                {"role": "assistant", "content": """{
                "Core Curriculum": {
                    "Introduction to Data Analysis": ["What is data analysis?", "The data analysis process", "Data types and structures"],
                    "Data Wrangling": ["Data cleaning", "Data transformation", "Data integration"],
                    "Statistical Analysis": ["Descriptive statistics", "Inferential statistics", "Regression analysis"],
                    "Machine Learning": ["Supervised learning", "Unsupervised learning", "Deep learning"],
                    "Data Visualization": ["Creating data visualizations", "Interpreting data visualizations"]
                },
                "Technical Skills": {
                    "Programming": ["Python", "SQL"],
                    "Data Science Tools": ["R", "Tableau", "Power BI"],
                    "Cloud Computing": ["AWS", "Azure", "Google Cloud Platform"]
                },
                "Soft Skills": {
                    "Communication": ["Presenting data", "Writing reports"],
                    "Problem Solving": ["Identifying problems", "Developing solutions"],
                    "Critical Thinking": ["Analyzing data", "Making decisions"],
                    "Teamwork": ["Working with others", "Collaborating on projects"]
                }
                }"""},
                {"role": "user", "content": "Please design for me a curriculum for being a " +carreer+". Provide it in a json format"}
            ]
            )

            string = str(completion.choices[0].message['content'])
            first_curly = string.find('{')
            last_curly = string.rfind('}')
            string = string[first_curly:last_curly+1]

            loaded_json = json.loads(re.sub(' +', ' ', string.replace('\n','')).replace(', }','}').replace(',}','}'))

            ruta_educativa = []

            for seccion in loaded_json.keys():
                seccion_actual = loaded_json[seccion]

                if type(seccion_actual) == dict:
                    subsecciones = seccion_actual.keys()
                elif type(seccion_actual) == list:
                    subsecciones = seccion_actual
                else:
                    subsecciones = seccion_actual.keys()

                for subseccion in subsecciones:
                    if type(seccion_actual) == dict:
                        subseccion_actual = seccion_actual[subseccion]
                    else:
                        subseccion_actual = subseccion
                    if type(subseccion_actual) == str:
                        row = {}
                        videosSearch = VideosSearch(subseccion, limit = 1)
                        result = videosSearch.result()['result'][0]
                        row['seccion'] = [seccion]
                        row['tema'] = [subseccion]
                        row['titulo_video'] = [result['title']]
                        row['url_video'] = [result['link']]
                    else:
                        for tema in subseccion_actual:
                            row = {}
                            videosSearch = VideosSearch(tema, limit = 1)
                            result = videosSearch.result()['result'][0]
                            row['seccion'] = [seccion]
                            row['subseccion'] = [subseccion]
                            row['tema'] = [tema]
                            row['titulo_video'] = [result['title']]
                            row['url_video'] = [result['link']]

                    ruta_educativa.append(row)

            tries = 0

            while tries < 5:
                try:
                    download_from_s3('rutas_educativas','/app/pkl-data/')
                    rutas_educativas = load_from_local('rutas_educativas')
                    temp_dict = {}
                    temp_dict['ruta']=ruta_educativa
                    rutas_educativas[id_user] = temp_dict
                    save_to_local(rutas_educativas, 'rutas_educativas')
                    save_to_s3(rutas_educativas, 'rutas_educativas')
                    break
                except Exception as e:
                    print(e)
                    tries += 1
                    continue

            # rutas_educativas = {}
            # temp_dict = {}
            # temp_dict['ruta']=ruta_educativa
            # rutas_educativas[id_user] = temp_dict
            # save_to_local(rutas_educativas, 'rutas_educativas')
            # save_to_s3(rutas_educativas, 'rutas_educativas')
            # break
            break
        except Exception as e:
            print('ERROR GENERANDO RUTA EDUCATIVA')
            print(e)
            print('REINTENTANDO {}'.format(tries))
            tries1 +=1
            continue

@app.get("/{role}")
def post_ruta_educativa(role: str):
    
    # role = role.replace('_', ' ')

    # token = 'XAjmxb_yUG3YuN-LYn-vqzvHh7wMrRdyjgalK3-KYHHsvodXv_LsYDV0rChI8l3r7N_JyQ.'
    # query = '''imagine you are a curriculum designer. Please design for me a curriculum for being a '''+role+'''. Provide it in a json format like this example {
    # "Core Curriculum": {
    #     "Introduction to Data Analysis": ["What is data analysis?", "The data analysis process", "Data types and structures"],
    #     "Data Wrangling": ["Data cleaning", "Data transformation", "Data integration"],
    #     "Statistical Analysis": ["Descriptive statistics", "Inferential statistics", "Regression analysis"],
    #     "Machine Learning": ["Supervised learning", "Unsupervised learning", "Deep learning"],
    #     "Data Visualization": ["Creating data visualizations", "Interpreting data visualizations"]
    # },
    # "Technical Skills": {
    #     "Programming": ["Python", "SQL"],
    #     "Data Science Tools": ["R", "Tableau", "Power BI"],
    #     "Cloud Computing": ["AWS", "Azure", "Google Cloud Platform"]
    # },
    # "Soft Skills": {
    #     "Communication": ["Presenting data", "Writing reports"],
    #     "Problem Solving": ["Identifying problems", "Developing solutions"],
    #     "Critical Thinking": ["Analyzing data", "Making decisions"],
    #     "Teamwork": ["Working with others", "Collaborating on projects"]
    # }
    # }'''

    

    # bard = Bard(token=token)
    # bard.get_answer(query)['content']

    # string = bard.get_answer(query)['content']

    openai.api_key = "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"
    carreer = role

    completion = openai.ChatCompletion.create(
    model = "gpt-3.5-turbo",
    max_tokens = 2000,
    messages = [
        {"role": "system", "content": "You are a curriculum designer."},
        {"role": "user", "content": "Please design for me a curriculum for being a data analyst. Provide it in a json format"},
        {"role": "assistant", "content": """{
        "Core Curriculum": {
            "Introduction to Data Analysis": ["What is data analysis?", "The data analysis process", "Data types and structures"],
            "Data Wrangling": ["Data cleaning", "Data transformation", "Data integration"],
            "Statistical Analysis": ["Descriptive statistics", "Inferential statistics", "Regression analysis"],
            "Machine Learning": ["Supervised learning", "Unsupervised learning", "Deep learning"],
            "Data Visualization": ["Creating data visualizations", "Interpreting data visualizations"]
        },
        "Technical Skills": {
            "Programming": ["Python", "SQL"],
            "Data Science Tools": ["R", "Tableau", "Power BI"],
            "Cloud Computing": ["AWS", "Azure", "Google Cloud Platform"]
        },
        "Soft Skills": {
            "Communication": ["Presenting data", "Writing reports"],
            "Problem Solving": ["Identifying problems", "Developing solutions"],
            "Critical Thinking": ["Analyzing data", "Making decisions"],
            "Teamwork": ["Working with others", "Collaborating on projects"]
        }
        }"""},
        {"role": "user", "content": "Please design for me a curriculum for being a " +carreer+". Provide it in a json format"}
    ]
    )

    string = str(completion.choices[0].message['content'])


    first_curly = string.find('{')
    last_curly = string.rfind('}')
    string = string[first_curly:last_curly+1]

    loaded_json = json.loads(re.sub(' +', ' ', string.replace('\n','')).replace(', }','}').replace(',}','}'))

    ruta_educativa = []

    for seccion in loaded_json.keys():
        seccion_actual = loaded_json[seccion]

        if type(seccion_actual) == dict:
            subsecciones = seccion_actual.keys()
        elif type(seccion_actual) == list:
            subsecciones = seccion_actual
        else:
            subsecciones = seccion_actual.keys()

        for subseccion in subsecciones:
            if type(seccion_actual) == dict:
                subseccion_actual = seccion_actual[subseccion]
            else:
                subseccion_actual = subseccion
            if type(subseccion_actual) == str:
                row = {}
                videosSearch = VideosSearch(subseccion, limit = 1)
                result = videosSearch.result()['result'][0]
                row['seccion'] = [seccion]
                row['tema'] = [subseccion]
                row['titulo_video'] = [result['title']]
                row['url_video'] = [result['link']]
            else:
                for tema in subseccion_actual:
                    row = {}
                    videosSearch = VideosSearch(tema, limit = 1)
                    result = videosSearch.result()['result'][0]
                    row['seccion'] = [seccion]
                    row['subseccion'] = [subseccion]
                    row['tema'] = [tema]
                    row['titulo_video'] = [result['title']]
                    row['url_video'] = [result['link']]

            ruta_educativa.append(row)
    return ruta_educativa

@app.get("/ruta_educativa/{user_id}")
def get_ruta_educativa(user_id: str):
    tries = 0
    while tries < 5:
        try:
            rutas_educativas = pkl.load(open('/app/pkl-data/rutas_educativas.pkl','rb'))
            return rutas_educativas[user_id]
            break
        except Exception as e:
            print(e)
            tries += 1
            continue
    return{"message":"error"}

@app.on_event("startup")
async def startup():
    site.mount_app(app)
    download_from_s3('chatgpt_responses','/app/pkl-data/')
    download_from_s3('rutas_educativas','/app/pkl-data/')
    scheduler.start()