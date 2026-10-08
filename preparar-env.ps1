# =============================================================================
#  preparar-env.ps1 - el .env de APOFYX, con secretos al azar
# =============================================================================
#  Los secretos no tienen valor por omision en el repositorio: un valor escrito
#  ahi seria publico. Este script los genera en tu .env, que no se sube.
#
#    .\preparar-env.ps1
#        Crea el .env desde .env.example si no existe, y completa cada secreto
#        que falte o este vacio. Lo que ya tiene valor no se toca.
#
#    .\preparar-env.ps1 -Renovar
#        Ademas cambia los secretos que todavia tengan uno de los valores de
#        desarrollo que antes venian escritos en el repositorio (los reconoce
#        por su huella SHA-256, sin guardarlos aqui). La clave del panel se
#        cambia tambien en el usuario que ya existe, y las de MySQL dentro de
#        la base, si los contenedores estan arriba, sin perder datos.
#
#    .\preparar-env.ps1 -Renovar -TambienCifrado
#        Lo mismo, y tambien CIFRADO_LLAVE. Cuidado: con ella se cifran la clave
#        de DataBridge y los secretos de los avisos; despues de cambiarla hay que
#        volver a conectar la plataforma, y las empresas vuelven a registrar su
#        direccion de avisos.
#
#    .\preparar-env.ps1 -Cambiar DJANGO_SUPERUSER_PASSWORD[,OTRO]
#        Cambia esos secretos aunque ya tengan un valor propio: para cuando uno
#        se filtro (quedo en una captura, en un registro, en un chat).
#
#  Nunca muestra un valor. Despues: docker compose --profile app up -d.
# =============================================================================
param(
    [switch]$Renovar,
    [switch]$TambienCifrado,
    [string[]]$Cambiar = @(),
    #  Los contenedores de APOFYX. Solo cambian en una prueba.
    [string]$ContenedorBase = 'apofyx-db',
    [string]$ContenedorWeb = 'apofyx-web'
)

$ErrorActionPreference = 'Stop'
$archivo = Join-Path $PSScriptRoot '.env'
$ejemplo = Join-Path $PSScriptRoot '.env.example'
$sinBom = New-Object System.Text.UTF8Encoding($false)

#  Los secretos, en este orden, y la huella SHA-256 del valor publico que tenia
#  cada uno. La clave del panel va primero: para cambiarla en el usuario hace
#  falta que la aplicacion todavia entre a MySQL con la clave de antes.
#  DB_PASSWORD no esta: es siempre la misma que MYSQL_PASSWORD.
$secretos = [ordered]@{
    DJANGO_SUPERUSER_PASSWORD = 'bca14fa23fc6913ffff94c84c414d6b68afcbacca315bfdcb886b56af9e9962d'
    DJANGO_SECRET_KEY         = 'd188294f5151b2e2cac75fdd2d70aa280571d61e89e8ef40396c877647cea5f1'
    CIFRADO_LLAVE             = 'a22b61dbbc876dd081f8313ffd82748f02f8ae594ac490c5b1027244cbd37fe9'
    MYSQL_PASSWORD            = '638fc1f3a4843d41797cb4156c9513b13d894095a2ddde8cb5eade4e45655d67'
    MYSQL_ROOT_PASSWORD       = '5012f5182061c46e57859cf617128c6f70eddfba4db27772bdede5a039fa7085'
}

function Nueva-Clave {
    #  48 bytes al azar del generador criptografico, en base64 sin + / ni =:
    #  nada que rompa un .env, una URL, una linea de SQL o la de comandos.
    $bytes = New-Object byte[] 48
    $generador = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $generador.GetBytes($bytes)
    $generador.Dispose()
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Huella([string]$texto) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $hash = $sha.ComputeHash($sinBom.GetBytes($texto))
    $sha.Dispose()
    return -join ($hash | ForEach-Object { $_.ToString('x2') })
}

function Valor([System.Collections.Generic.List[string]]$lineas, [string]$nombre) {
    foreach ($linea in $lineas) {
        if ($linea -match "^\s*$nombre\s*=(.*)$") { return $Matches[1].Trim() }
    }
    return $null
}

function Poner([System.Collections.Generic.List[string]]$lineas, [string]$nombre, [string]$valor) {
    for ($i = 0; $i -lt $lineas.Count; $i++) {
        if ($lineas[$i] -match "^\s*$nombre\s*=") { $lineas[$i] = "$nombre=$valor"; return }
    }
    $lineas.Add("$nombre=$valor")
}

function Arriba([string]$contenedor) {
    $antes = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $estado = docker inspect -f '{{.State.Running}}' $contenedor 2>$null
    $ok = ($LASTEXITCODE -eq 0 -and $estado -eq 'true')
    $ErrorActionPreference = $antes
    return $ok
}

#  Corre un comando en un contenedor con su entrada por stdin y las variables
#  que se le pasan por el entorno: ninguna clave queda en la linea de comandos,
#  donde cualquier proceso del equipo la podria leer. En PowerShell 5.1 lo que
#  un programa escribe en stderr corta el script si la preferencia es Stop: aqui
#  se mira el codigo de salida.
function En-Contenedor([string]$contenedor, [hashtable]$variables, [string]$entrada, [string[]]$comando) {
    $antes = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $argumentos = @('exec', '-i')
    foreach ($nombre in $variables.Keys) {
        Set-Item "Env:$nombre" $variables[$nombre]
        $argumentos += @('-e', $nombre)
    }
    try {
        $salida = $entrada | & docker @($argumentos + @($contenedor) + $comando) 2>$null
        return ($LASTEXITCODE -eq 0), ($salida -join "`n")
    } finally {
        foreach ($nombre in $variables.Keys) { Remove-Item "Env:$nombre" -ErrorAction SilentlyContinue }
        $ErrorActionPreference = $antes
    }
}

if (-not (Test-Path $archivo)) {
    Copy-Item $ejemplo $archivo
    Write-Host "Cree el .env desde .env.example."
}
$lineas = New-Object System.Collections.Generic.List[string]
foreach ($linea in [System.IO.File]::ReadAllLines($archivo, $sinBom)) { $lineas.Add($linea) }

$tocaContenedores = $Renovar -or $Cambiar.Count -gt 0
$baseArriba = $tocaContenedores -and (Arriba $ContenedorBase)
$webArriba = $tocaContenedores -and (Arriba $ContenedorWeb)
$rootActual = Valor $lineas 'MYSQL_ROOT_PASSWORD'
$usuarioBase = Valor $lineas 'MYSQL_USER'
if (-not $usuarioBase) { $usuarioBase = 'apofyx_app' }
$usuarioPanel = Valor $lineas 'DJANGO_SUPERUSER_USERNAME'
if (-not $usuarioPanel) { $usuarioPanel = 'admin' }

foreach ($nombre in $secretos.Keys) {
    $actual = Valor $lineas $nombre
    if (-not $actual) {
        $nueva = Nueva-Clave
        Poner $lineas $nombre $nueva
        if ($nombre -eq 'MYSQL_PASSWORD') { Poner $lineas 'DB_PASSWORD' $nueva }
        Write-Host "$nombre`: generado."
        continue
    }
    $forzado = $Cambiar -contains $nombre
    if ((Huella $actual) -ne $secretos[$nombre] -and -not $forzado) {
        Write-Host "$nombre`: ya tiene un valor propio, no se toca."
        continue
    }
    if (-not $Renovar -and -not $forzado) {
        Write-Host "$nombre`: tiene el valor publico de antes. Cambialo con -Renovar." -ForegroundColor Yellow
        continue
    }
    if ($nombre -eq 'CIFRADO_LLAVE' -and -not $TambienCifrado -and -not $forzado) {
        Write-Host "CIFRADO_LLAVE: tiene el valor publico de antes. No la cambio sin -TambienCifrado (habria que volver a conectar la plataforma y las empresas)." -ForegroundColor Yellow
        continue
    }
    $nueva = Nueva-Clave

    if ($nombre -eq 'DJANGO_SUPERUSER_PASSWORD') {
        if (-not $webArriba) {
            Write-Host "$nombre`: la aplicacion no esta arriba (docker compose --profile app up -d); vuelve a correr con -Renovar." -ForegroundColor Yellow
            continue
        }
        #  En una sola linea y sin comillas dobles: PowerShell 5.1 rompe las comillas
        #  de un argumento, y por la entrada estandar le antepone un BOM que Python
        #  rechaza. La clave nueva viaja en el entorno (NUEVA), no en el codigo.
        $codigo = "import os; from django.contrib.auth import get_user_model; u = get_user_model().objects.filter(username=os.environ['USUARIO']).first(); u and u.set_password(os.environ['NUEVA']); u and u.save(); print('cambiada' if u else 'no-existe')"
        $ok, $salida = En-Contenedor $ContenedorWeb @{ USUARIO = $usuarioPanel; NUEVA = $nueva } '' @('python', 'manage.py', 'shell', '-c', $codigo)
        if (-not $ok -or ($salida -notmatch 'cambiada|no-existe')) {
            Write-Host "$nombre`: no pude cambiarla en el usuario; el .env queda como estaba." -ForegroundColor Red
            continue
        }
    }

    if ($nombre -like 'MYSQL_*') {
        if (-not $baseArriba) {
            Write-Host "$nombre`: la base no esta arriba (docker compose up -d); vuelve a correr con -Renovar." -ForegroundColor Yellow
            continue
        }
        if ($nombre -eq 'MYSQL_ROOT_PASSWORD') {
            $sql = "ALTER USER IF EXISTS 'root'@'%' IDENTIFIED BY '$nueva'; ALTER USER IF EXISTS 'root'@'localhost' IDENTIFIED BY '$nueva';"
        } else {
            $sql = "ALTER USER IF EXISTS '$usuarioBase'@'%' IDENTIFIED BY '$nueva';"
        }
        $ok, $salida = En-Contenedor $ContenedorBase @{ MYSQL_PWD = $rootActual } $sql @('mysql', '-uroot')
        if (-not $ok) {
            Write-Host "$nombre`: MySQL no acepto el cambio; el .env queda como estaba." -ForegroundColor Red
            continue
        }
        if ($nombre -eq 'MYSQL_ROOT_PASSWORD') { $rootActual = $nueva }
        if ($nombre -eq 'MYSQL_PASSWORD') { Poner $lineas 'DB_PASSWORD' $nueva }
    }

    Poner $lineas $nombre $nueva
    Write-Host "$nombre`: renovado." -ForegroundColor Green
}

#  DB_PASSWORD es la misma clave que MYSQL_PASSWORD, vista desde Django.
$deLaBase = Valor $lineas 'MYSQL_PASSWORD'
if ($deLaBase -and (Valor $lineas 'DB_PASSWORD') -ne $deLaBase) {
    Poner $lineas 'DB_PASSWORD' $deLaBase
    Write-Host "DB_PASSWORD: igualada a MYSQL_PASSWORD."
}

[System.IO.File]::WriteAllLines($archivo, $lineas, $sinBom)
Write-Host ""
Write-Host "Listo. Para que los contenedores tomen los valores: docker compose --profile app up -d"
exit 0
