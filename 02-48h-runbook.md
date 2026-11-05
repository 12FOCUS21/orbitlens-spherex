# Runbook de 48 horas

La inscripción está abierta y el hackathon global 2026 ocurre el **14–15 de noviembre**. La entrega cierra el 15 de noviembre a las 23:59 hora local de cada equipo según la información de Space Apps. [Cronograma oficial](https://www.spaceappschallenge.org/2026/)

## Antes del evento: preparación permitida, no producto preconstruido

| Cuándo | Acción | Salida |
| --- | --- | --- |
| Hoy | Confirmar reglas con el Local Lead; cada integrante acepta las condiciones | decisión registrada en issue #0 |
| T-7 a T-2 días | Repartir roles, estudiar documentación pública y ensayar Git | equipo operativo; no código de la solución |
| T-2 días | Verificar herramientas, cuentas, conectividad, licencia y formato de entrega | checklist preflight |
| T-1 día | Redactar hipótesis de producto y criterios de aceptación; elegir horario de reunión | acta y agenda |

No hay que asumir que trabajo o código previo está permitido. Usen las condiciones 2026 y la indicación del evento local como autoridad; en caso de duda, declaren el material preexistente o no lo usen.

## Durante el hackathon

| Tiempo | Meta no negociable | Responsable principal | Criterio de salida |
| --- | --- | --- | --- |
| T+0–2 h | alineamiento y elección de las 3 regiones | Product + Ciencia | PR con alcance congelado y fuentes iniciales |
| T+2–6 h | prueba de datos y «thin slice» | Datos + Frontend | una región visible, dos épocas, cita desplegada |
| T+6–12 h | comparador estable | Frontend + QA | blink, slider y diferencia para un caso |
| T+12–18 h | candidatas y narrativa | QA + Diseño | tarjeta de evidencia y guion de 90 segundos |
| **T+18 h** | **corte del MVP** | Todo el equipo | lo anterior desplegado y probado; solo bugs después |
| T+18–30 h | 2 regiones más, accesibilidad y fuentes | Roles por área | demo completa aun sin internet |
| T+30–38 h | ensayo de pitch, video y pulido | Diseño + Product | video y presentación en versión candidata |
| T+38–44 h | pruebas finales y documentación | QA + todos | README, créditos, licencia y enlaces validados |
| T+44–48 h | envío con margen | Product owner | submission enviada y comprobada |

## Cadencia de equipo

- **Stand-up de 10 min cada 3 h:** qué se hizo, qué bloquea, qué se hará. Quien facilita rota.
- **Mesa de decisiones:** Product owner decide alcance; Ciencia puede bloquear afirmaciones no sustentadas; QA puede bloquear una demo rota.
- **Regla de los 20 min:** si un bloqueo técnico dura 20 minutos, se pide ayuda en el canal del equipo y se activa un plan B.
- **Dos zonas horarias o descansos:** mantengan un tablero con estado y enlaces; nadie depende de mensajes privados para continuar.

## Definition of Done para el MVP

- El flujo completo inicia desde una URL limpia y llega a una tarjeta de evidencia.
- Las dos imágenes representan épocas y bandas identificadas o están señaladas como simulación.
- La interfaz funciona con ratón y teclado básico, sin errores de consola visibles.
- El README reproduce la demo y nombra cada fuente externa.
- Una persona que no construyó la función la prueba y aprueba.
