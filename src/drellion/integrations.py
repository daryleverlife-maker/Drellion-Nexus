from dataclasses import dataclass

@dataclass
class IntegrationState:
    name:str
    enabled:bool=False
    status:str='Not connected'

DEFAULT_INTEGRATIONS=[
    IntegrationState('Suno'),
    IntegrationState('Mureka'),
    IntegrationState('Discord'),
    IntegrationState('Google'),
    IntegrationState('YouTube Reference'),
    IntegrationState('Genius Lyrics'),
]
