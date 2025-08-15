                    else:
                        # NO MAS FALLBACKS - SIN DATOS = FALLA CRITICA
                        raise Exception("FORMAS DE PAGO REQUERIDAS - No se recibieron datos válidos")
                        
        except Exception as e:
            print(f"Error critico en procesamiento de formas de pago: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            # NO MAS FALLBACKS - ERROR CRITICO DEBE DETENER TODO
            raise Exception(f"PROCESAMIENTO DE FORMAS DE PAGO FALLÓ: {e}")
