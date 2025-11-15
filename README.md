# Robot de Limpieza Reactivo - Sistema Multiagentes

Simulación de robots de limpieza reactivos usando Mesa (Python Agent-Based Modeling)

## Descripción

Este proyecto implementa un sistema multiagentes donde robots autónomos limpian una habitación de forma reactiva. Los robots utilizan un comportamiento simple:
- Si la celda actual está sucia → la limpian
- Si la celda está limpia → se mueven aleatoriamente a una celda vecina

El proyecto fue desarrollado como parte del curso **TC2008B - Modelación de Sistemas Multiagentes con Gráficas Computacionales** en el Tecnológico de Monterrey.

## Objetivo

Conocer y aplicar una herramienta para la implementación de sistemas multiagentes utilizando el framework Mesa de Python.

## Características

- **Agentes reactivos**: Los robots toman decisiones basadas únicamente en su percepción local
- **Grilla configurable**: Tamaño de habitación personalizable (MxN)
- **Métricas en tiempo real**: Recopilación de datos durante la simulación
- **Visualización**: Gráficas de evolución del proceso de limpieza
- **Parámetros ajustables**: Número de agentes, porcentaje de suciedad inicial, tiempo máximo

## Métricas Recopiladas

Durante la ejecución, el modelo recopila las siguientes estadísticas:

1. **Tiempo de limpieza**: Pasos necesarios hasta que todas las celdas están limpias (o se alcanza el máximo)
2. **Porcentaje de celdas limpias**: Evolución del % de limpieza en cada paso
3. **Movimientos totales**: Suma de movimientos de todos los robots
4. **Movimientos por agente**: Registro individual de cada robot

## Tecnologías Utilizadas

- **Python 3.x**
- **Mesa**: Framework para modelado basado en agentes
- **Matplotlib**: Visualización de datos
- **NumPy**: Operaciones numéricas
- **Google Colab**: Entorno de desarrollo

## Instalación

### Requisitos

```bash
pip install mesa matplotlib numpy
```

### Ejecución en Google Colab

1. Abre el notebook en Google Colab
2. Ejecuta la primera celda para instalar dependencias:
   ```python
   !pip install mesa -q
   ```
3. Ejecuta todas las celdas en orden (Runtime > Run All)

## Uso

### Parámetros del Modelo

```python
modelo = CleaningModel(
    num_agentes=5,          # Número de robots
    width=10,               # Ancho de la habitación
    height=10,              # Alto de la habitación
    porcentaje_sucias=0.4,  # 40% de celdas inicialmente sucias
    max_steps=200,          # Máximo de pasos de simulación
    seed=42                 # Semilla para reproducibilidad
)
```

### Ejecutar Simulación

```python
# Ejecutar el modelo
modelo.run_model()

# Obtener resultados
print(f"Pasos ejecutados: {modelo.steps}")
print(f"Porcentaje limpio: {calcular_porcentaje_limpio(modelo):.2f}%")
print(f"Movimientos totales: {contar_movimientos_totales(modelo)}")
```

## Resultados Ejemplo

Con una configuración de **5 robots** en una habitación **10x10** con **40% de suciedad**:

- **Pasos para limpiar**: ~110-130 pasos (promedio)
- **Movimientos totales**: ~450-500 movimientos
- **Eficiencia**: El porcentaje de limpieza crece rápidamente al inicio y se estabiliza al final

### Gráficas

El modelo genera visualizaciones automáticas mostrando:
- Evolución de celdas sucias vs tiempo
- Evolución del porcentaje de limpieza vs tiempo

## Análisis

### Impacto del Número de Agentes

- **Menos agentes (3-5)**: Mayor tiempo para limpiar, menor número de movimientos totales
- **Más agentes (10-15)**: Menor tiempo para limpiar, mayor número de movimientos totales
- **Trade-off**: Existe un punto óptimo entre tiempo y recursos (número de robots)

### Impacto del Tamaño de la Habitación

- Habitaciones más grandes requieren proporcionalmente más pasos
- El movimiento aleatorio puede ser ineficiente en espacios grandes
- Se recomienda ajustar el número de agentes según el área total

## Estructura del Proyecto

```
.
├── Robot_Limpieza_Mesa.ipynb    # Notebook principal con el modelo
└── README.md                     # Este archivo
```

## Arquitectura del Modelo

### Clases Principales

1. **CeldaHabitacion**: Representa el estado de cada celda (sucia/limpia)
2. **RobotLimpieza**: Agente que se mueve y limpia
3. **CleaningModel**: Modelo principal que coordina la simulación

### Flujo de Ejecución

```
1. Inicialización
   ├─ Crear grilla MxN
   ├─ Ensuciar celdas aleatoriamente
   └─ Crear robots en posición inicial

2. Loop de Simulación
   ├─ Cada robot ejecuta su step()
   │  ├─ ¿Celda sucia? → Limpiar
   │  └─ ¿Celda limpia? → Moverse aleatoriamente
   └─ Recopilar métricas

3. Finalización
   ├─ Todas las celdas limpias, O
   └─ Se alcanzó el máximo de pasos
```

## Estándar de Codificación

El código sigue el estándar de codificación del Tecnológico de Monterrey:

- Nombres descriptivos en camelCase
- Comentarios con valor agregado
- Documentación de funciones y métodos
- Estructura clara y modular
- Una tarea por función/método

## Autores

- **[Tu Nombre]** - [Tu Matrícula]
- **[Compañero si aplica]** - [Matrícula]

## Fecha

Noviembre 2024

## Curso

**TC2008B - Modelación de Sistemas Multiagentes con Gráficas Computacionales**  
Tecnológico de Monterrey

## Referencias

- [Mesa Documentation](https://mesa.readthedocs.io/)
- [Mesa GitHub Repository](https://github.com/projectmesa/mesa)
- Epstein, J. M., & Axtell, R. (1996). Growing Artificial Societies: Social Science from the Bottom Up

## Licencia

Este proyecto fue desarrollado con fines educativos para el Tecnológico de Monterrey.

---

**Nota**: Este es un proyecto académico desarrollado para aprender sobre sistemas multiagentes y modelado basado en agentes.
