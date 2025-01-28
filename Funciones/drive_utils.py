#Funciones/drive_utils.py

import os
import json
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import googleapiclient.http
import streamlit as st

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    creds = None
    try:
        secret_string = os.environ['GOOGLE_CLIENT_SECRET']
        print(f"String del Secret antes de json.loads(): {secret_string}")
        client_secret = json.loads(secret_string)
        print(f"Diccionario client_secret: {client_secret}")

        if "web" in client_secret: #Cambiar installed por web
            client_config = client_secret["web"]
        else:
            print("Error: El JSON del secret no contiene la clave 'web'")
            return None
    except KeyError as e:
        print(f"Error: Variable de entorno GOOGLE_CLIENT_SECRET no encontrada: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: JSON en GOOGLE_CLIENT_SECRET inválido: {e}")
        print(f"String del secret: {secret_string}")
        return None
    except TypeError as e:
        print(f"Error: el valor del secret no es un diccionario: {e}")
        return None
    except Exception as e:
        print(f"Error desconocido: {e}")
        return None

    

    redirect_uri = f"https://{os.environ['REPL_SLUG']}.{os.environ['REPL_OWNER']}.repl.co/callback"
    flow = Flow.from_client_config(
        client_config, scopes=SCOPES, redirect_uri=redirect_uri #Añadir redirect_uri
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    st.write(f"Por favor, autoriza la aplicación accediendo a este enlace: {authorization_url}")

    authorization_response = st.experimental_get_query_params().get("code")
    if authorization_response:
        try:
            flow.fetch_token(authorization_response=authorization_response)
            creds = flow.credentials

            service = build('drive', 'v3', credentials=creds)
            return service
        except Exception as e:
            print(f"Error al obtener el token: {e}")
            return None
    else:
        st.write("Esperando autorización...")
        st.stop()
    return None

def guardar_en_drive(service, nombre_archivo_json, contenido_json):
    """Guarda un archivo JSON en Google Drive."""
    try:
        file_metadata = {'name': nombre_archivo_json, 'mimeType': 'application/json'}
        media = googleapiclient.http.MediaIoBaseUpload(
            io.BytesIO(json.dumps(contenido_json).encode()),
            mimetype='application/json'
        )
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"Archivo creado con ID: {file.get('id')}")
        st.success("Los datos se han guardado exitosamente en Google Drive")
        return file.get('id')
    except Exception as e:
        print(f"Error al guardar el archivo en Drive: {e}")
        st.error("Ocurrió un error al guardar los datos en Google Drive")
        return None
