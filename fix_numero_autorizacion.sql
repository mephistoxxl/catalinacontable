-- SQL para ampliar el campo numero_autorizacion de GuiaRemision
-- Ejecutar directamente en la base de datos PostgreSQL

ALTER TABLE guia_remision 
ALTER COLUMN numero_autorizacion TYPE VARCHAR(49);

-- Verificar el cambio
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE table_name = 'guia_remision' 
AND column_name = 'numero_autorizacion';
