# Reglas Operativas del Agente

- En cada `push` que incluya cambios de base de datos (migraciones, SQL, o cambios de schema), dejar explicito en el PR/nota de cambios que, luego de hacer `pull` en otra maquina, hay que ejecutar los `apply` de DB correspondientes.
- Ademas de eso, siempre reflejar los cambios en el schema.
