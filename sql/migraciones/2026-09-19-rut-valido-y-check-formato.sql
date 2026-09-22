-- =============================================================================
--  2026-09-19 — RUT validos y CHECK de formato sobre crm_creditor.tax_id
-- =============================================================================
--  POR QUE EXISTE ESTE ARCHIVO
--  AphofyxDB.sql solo se ejecuta cuando el volumen de Docker esta vacio, asi
--  que un cambio en el DDL no llega a una base que ya esta andando. Este script
--  lleva ese cambio a una base existente, sin borrar datos.
--
--  QUE ARREGLA
--  1. Los cinco RUT de demostracion tenian el digito verificador inventado.
--     Ninguno pasaba el modulo 11, y el RUT es la llave con la que la empresa
--     acreedora se identifica fuera de APOFYX: con estos valores, las cinco
--     empresas serian rechazadas por cualquier sistema que lo valide.
--  2. Faltaba el CHECK que obliga el formato normalizado del RUT.
--
--  COMO SE EJECUTA
--      docker compose exec -T db mysql --default-character-set=utf8mb4 \
--          -u root -p"$MYSQL_ROOT_PASSWORD" apofyx \
--          < sql/migraciones/2026-09-19-rut-valido-y-check-formato.sql
--
--  --default-character-set=utf8mb4 NO es decorativo. Sin esa bandera el cliente
--  usa la codificacion de la consola —en Windows, cp850— y el patron del CHECK
--  queda guardado como literal cp850 dentro de una tabla utf8mb4. El patron es
--  ASCII y funciona igual, pero deja una mezcla de codificaciones adentro de una
--  restriccion, que despues aparece como un error de collation dificil de ubicar.
--  Es la misma razon por la que AphofyxDB.sql trae SET NAMES utf8mb4 adentro.
--
--  Es idempotente: se puede correr dos veces sin romper nada.
-- =============================================================================

USE apofyx;

-- -----------------------------------------------------------------------------
--  1. Digitos verificadores correctos
--
--  Instituto Andes cambia de cuerpo ademas de digito: se eligio 77812341,
--  cuyo verificador si es K, para conservar un RUT terminado en K entre los
--  datos de demostracion.
-- -----------------------------------------------------------------------------
UPDATE crm_creditor SET tax_id = '76543210-3' WHERE tax_id = '76543210-1';
UPDATE crm_creditor SET tax_id = '77812341-K' WHERE tax_id = '77812345-K';
UPDATE crm_creditor SET tax_id = '76998877-7' WHERE tax_id = '76998877-5';
UPDATE crm_creditor SET tax_id = '78123456-7' WHERE tax_id = '78123456-3';
UPDATE crm_creditor SET tax_id = '77456789-5' WHERE tax_id = '77456789-2';

-- -----------------------------------------------------------------------------
--  2. CHECK de formato
--
--  Va despues de los UPDATE a proposito: con los RUT viejos algunos pasarian
--  igual (el formato era valido aunque el digito fuera falso), pero el orden
--  correcto es dejar los datos buenos antes de imponer la regla.
--
--  El digito verificador NO se valida aca: el modulo 11 es aritmetica y un
--  CHECK con REGEXP no lo alcanza. Eso lo valida el formulario.
-- -----------------------------------------------------------------------------
SET @ya_existe = (
    SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
     WHERE CONSTRAINT_SCHEMA = 'apofyx'
       AND CONSTRAINT_NAME   = 'ck_creditor_tax_id'
);
SET @sentencia = IF(@ya_existe > 0,
    'SELECT ''ck_creditor_tax_id ya estaba puesto'' AS aviso',
    'ALTER TABLE crm_creditor ADD CONSTRAINT ck_creditor_tax_id
        CHECK (tax_id REGEXP ''^[0-9]{7,8}-[0-9K]$'')'
);
PREPARE aplicar FROM @sentencia;
EXECUTE aplicar;
DEALLOCATE PREPARE aplicar;

-- -----------------------------------------------------------------------------
--  3. Verificacion
-- -----------------------------------------------------------------------------
SELECT id, trade_name, tax_id, status FROM crm_creditor ORDER BY id;

SELECT CONSTRAINT_NAME, CHECK_CLAUSE
  FROM information_schema.CHECK_CONSTRAINTS
 WHERE CONSTRAINT_SCHEMA = 'apofyx'
   AND CONSTRAINT_NAME LIKE 'ck_creditor%';
