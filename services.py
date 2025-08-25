import requests
import os
from dotenv import load_dotenv
import json
import logging
from typing import Dict, Optional, Union
from requests.exceptions import RequestException, Timeout
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configurar logging con más detalle
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def validar_identificacion(identificacion: str) -> Optional[str]:
    """Valida el formato de la identificación.

    Retorna el tipo de identificación (`'RUC'` o `'CEDULA'`) si es válida.
    """
    logger.debug(f"Iniciando validación de identificación: {identificacion}")
    if not identificacion or not isinstance(identificacion, str):
        logger.error(
            f"Identificación inválida: valor vacío o tipo incorrecto - {type(identificacion)}"
        )
        return None
    if not identificacion.isdigit():
        logger.error("Identificación inválida: contiene caracteres no numéricos")
        return None
    if len(identificacion) == 13:
        logger.debug("Identificación válida: RUC")
        return "RUC"
    if len(identificacion) == 10:
        logger.debug("Identificación válida: CÉDULA")
        return "CEDULA"
    logger.error(
        f"Identificación inválida: longitud {len(identificacion)} no permitida"
    )
    return None

def consultar_identificacion(identificacion: str) -> Dict[str, Union[str, bool]]:
    """Consulta información de RUC o cédula usando el API de Zampisoft."""
    logger.info(f"Consultando identificación: {identificacion}")

    tipo_identificacion = validar_identificacion(identificacion)
    if not tipo_identificacion:
        return {
            'error': True,
            'message': 'Identificación inválida: debe tener 10 o 13 dígitos',
            'status_code': 400
        }
    
    # URL de la API de Zampisoft
    url = "https://apiconsult.zampisoft.com/api/consultar"
    
    # Obtener token del archivo .env o usar el token por defecto
    token = os.getenv('ZAMPISOFT_TOKEN', 'wTGv-8Iqi-ckFW-A8bo')
    logger.info(f"Token a usar: {token[:4]}...{token[-4:]}")
    
    try:
        # Configurar los parámetros
        params = {
            "identificacion": identificacion,
            "token": token
        }
        
        # Mostrar información de la solicitud
        logger.info(f"URL de la API: {url}")
        logger.info(f"Parámetros de la solicitud: {json.dumps(params, indent=2)}")
        
        # Realizar la solicitud
        logger.info("Enviando solicitud a la API...")
        response = requests.get(url, params=params, timeout=15)
        
        # Mostrar información de la respuesta
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Headers de respuesta: {dict(response.headers)}")
        logger.info(f"URL final: {response.url}")
        logger.info(f"Contenido de la respuesta: {response.text[:1000]}")
        
        # Intentar parsear la respuesta como JSON
        try:
            data = response.json()
            logger.info(f"Respuesta JSON completa: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError as e:
            logger.error(f"Error al decodificar JSON: {str(e)}")
            logger.error(f"Respuesta recibida: {response.text[:500]}")
            return {
                'error': True,
                'message': 'Error al procesar la respuesta del servidor',
                'status_code': 500
            }
        
        # Verificar si hay error en la respuesta de la API
        api_error = data.get('error', False)
        api_message = data.get('message', 'Error desconocido de la API') if api_error else ''

        # Extraer dirección del primer establecimiento si existe
        direccion = ''
        establecimientos = data.get('establecimientos', [])
        if tipo_identificacion == 'RUC' and establecimientos:
            direccion = establecimientos[0].get('direccionCompleta', '')
            nombre_comercial = establecimientos[0].get(
                'nombreFantasiaComercial', ''
            )
        else:
            nombre_comercial = ''
            if tipo_identificacion == 'CEDULA':
                direccion = data.get('calleDomicilio', data.get('direccion', ''))
            else:
                direccion = data.get('direccionDomicilio', data.get('direccion', ''))

        # Mapear la respuesta al formato esperado
        tipo_contribuyente = data.get('tipoContribuyente')
        logger.info(f"Tipo de contribuyente original: {tipo_contribuyente}")

        # Mapear el tipo de contribuyente a los valores permitidos en el modelo.
        # Solo se aplica para consultas de RUC, ya que la API no entrega datos
        # de régimen para consultas con cédula y en esos casos no se debe
        # modificar el valor existente en el formulario.
        tipo_regimen_mapeado = None
        if tipo_contribuyente and tipo_identificacion == 'RUC':
            tipo_regimen_mapeado = (
                'RIMPE' if 'RIMPE' in tipo_contribuyente.upper() else 'GENERAL'
            )

        logger.info(f"Tipo de régimen mapeado: {tipo_regimen_mapeado}")
        
        # Mapear obligado a llevar contabilidad a SI/NO
        obligado_contabilidad = data.get('obligadoLlevarContabilidad', '')
        obligado_mapeado = 'SI' if obligado_contabilidad and obligado_contabilidad.upper() == 'SI' else 'NO'
        
        logger.info(f"Obligado a llevar contabilidad original: {obligado_contabilidad}, mapeado: {obligado_mapeado}")
        
        razon_social = data.get('razonSocial', '')
        if not razon_social:
            nombres = data.get('nombres', data.get('nombre', ''))
            apellidos = data.get('apellidos', data.get('apellido', ''))
            razon_social = f"{nombres} {apellidos}".strip()

        resultado = {
            'error': api_error,
            'message': api_message,
            'razon_social': razon_social,
            'nombre_comercial': nombre_comercial,
            'direccion': direccion,
            'telefono': data.get('telefono', ''),
            'email': data.get('email', ''),
            'tipo_contribuyente': tipo_contribuyente,
            'estado': data.get('estadoContribuyenteRuc', data.get('estado', '')),
            'obligado_contabilidad': obligado_mapeado,
            'actividad_economica': data.get('actividadEconomicaPrincipal', ''),
            'status_code': response.status_code,
            'tipo_identificacion': tipo_identificacion
        }

        if tipo_regimen_mapeado:
            resultado['tipo_regimen'] = tipo_regimen_mapeado
        
        logger.info(f"Resultado mapeado: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
        return resultado
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de conexión: {str(e)}")
        return {
            'error': True,
            'message': f'Error de conexión: {str(e)}',
            'status_code': 500
        }
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'error': True,
            'message': f'Error inesperado: {str(e)}',
            'status_code': 500
        }


# Las funciones de test siguen igual...
def test_consulta_identificacion():
    """Función de prueba para verificar la consulta de identificaciones."""
    # Identificación de prueba (puedes cambiar por una que sepas que existe)
    identificacion_prueba = "1713959011001"

    print(f"\n{'='*60}")
    print(f"PRUEBA DE CONSULTA IDENTIFICACIÓN: {identificacion_prueba}")
    print(f"{'='*60}\n")

    # Validar identificación
    tipo = validar_identificacion(identificacion_prueba)
    print(f"Tipo de identificación: {tipo}")

    if tipo:
        # Realizar consulta
        resultado = consultar_identificacion(identificacion_prueba)
        
        print("\nRESULTADO DE LA CONSULTA:")
        print("-" * 40)
        
        if resultado.get('error'):
            print(f"ERROR: {resultado.get('message')}")
            print(f"Código de estado: {resultado.get('status_code')}")
        else:
            print("CONSULTA EXITOSA")
            print("\nDatos obtenidos:")
            for campo, valor in resultado.items():
                if campo != 'error' and valor:
                    print(f"  {campo}: {valor}")
        
    print(f"\n{'='*60}\n")
    
    return resultado


def debug_api_response():
    """
    Función para debug detallado de la respuesta de la API
    """
    import requests
    
    # Configuración
    url = "https://apiconsult.zampisoft.com/api/consultar"
    params = {
        "identificacion": "1713959011001",  # RUC de prueba
        "token": "7a7R-zcYo-7pB9-hkqN"
    }
    
    print(f"\n{'='*60}")
    print("DEBUG DETALLADO DE LA API")
    print(f"{'='*60}\n")
    
    print(f"URL: {url}")
    print(f"Parámetros: {params}")
    
    try:
        # Hacer la solicitud
        response = requests.get(url, params=params, timeout=15)
        
        print(f"\nRespuesta:")
        print(f"  Status Code: {response.status_code}")
        print(f"  Headers: {dict(response.headers)}")
        print(f"  URL final: {response.url}")
        print(f"\nContenido de la respuesta:")
        print("-" * 40)
        print(response.text)
        print("-" * 40)
        
        # Intentar parsear como JSON
        try:
            data = response.json()
            print("\nDatos parseados como JSON:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except:
            print("\nNota: La respuesta no es JSON válido")
            
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*60}\n")

def test_api_directo(ruc=None):
    """
    Prueba directa de la API sin usar Django
    Args:
        ruc (str): El RUC a consultar. Si no se proporciona, se usará uno de prueba.
    """
    import requests
    import json
    
    # Si no se proporciona RUC, usar uno de prueba
    if not ruc:
        ruc = "1713959011001"
        print("\n⚠️  Usando RUC de prueba. Para probar con un RUC específico, llame a la función con el RUC como parámetro.")
        print("Ejemplo: test_api_directo('1234567890001')")
    
    # URL y parámetros
    url = "https://apiconsult.zampisoft.com/api/consultar"
    params = {
        "identificacion": ruc,
        "token": "wTGv-8Iqi-ckFW-A8bo"
    }
    
    print("\n" + "="*80)
    print("PRUEBA DIRECTA DE LA API")
    print("="*80)
    print(f"\nConsultando RUC: {ruc}")
    print(f"URL: {url}")
    print(f"Parámetros: {json.dumps(params, indent=2)}")
    
    try:
        # Realizar la solicitud
        response = requests.get(url, params=params, timeout=15)
        print(f"\nStatus Code: {response.status_code}")
        
        # Mostrar la respuesta completa
        print("\n" + "-"*80)
        print("RESPUESTA COMPLETA DE LA API:")
        print("-"*80)
        print(response.text)
        print("-"*80)
        
        # Intentar parsear como JSON
        try:
            data = response.json()
            print("\nDatos parseados como JSON:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Mostrar campos específicos
            print("\n" + "-"*80)
            print("CAMPOS ESPECÍFICOS:")
            print("-"*80)
            campos = [
                ('razonSocial', 'Razón Social'),
                ('nombreComercial', 'Nombre Comercial'),
                ('direccion', 'Dirección'),
                ('telefono', 'Teléfono'),
                ('email', 'Email'),
                ('tipoContribuyente', 'Tipo Contribuyente'),
                ('estado', 'Estado'),
                ('obligadoContabilidad', 'Obligado Contabilidad')
            ]
            
            for campo, nombre in campos:
                valor = data.get(campo, 'No encontrado')
                print(f"{nombre}: {valor}")
                
        except json.JSONDecodeError as e:
            print(f"\nError al parsear JSON: {str(e)}")
            print("La respuesta no es un JSON válido")
            
    except Exception as e:
        print(f"\nError en la solicitud: {str(e)}")
    
    print("\n" + "="*80)
    return data if 'data' in locals() else None

if __name__ == "__main__":
    # Ejemplo de uso:
    # test_api_directo()  # Usa RUC de prueba
    # test_api_directo('1234567890001')  # Usa RUC específico
    test_api_directo()
