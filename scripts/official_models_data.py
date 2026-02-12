#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Listado curado de modelos oficiales por marca, con fuentes públicas.
No pretende ser exhaustivo, sino cubrir las marcas y líneas más frecuentes
en la base actual para ayudar a detectar errores tipográficos y variantes.

Estructura:
OFFICIAL_MODELS = {
  'Marca': {
     'models': ['Nombre Modelo 1', 'Nombre Modelo 2', ...],
     'sources': ['https://url1', 'https://url2'],
     'notes': 'opcional'
  },
  ...
}
"""

OFFICIAL_MODELS = {
    'AirSep': {
        'models': [
            'NewLife', 'NewLife Elite', 'NewLife Intensity', 'VisionAire', 'VisionAire 5'
        ],
        'sources': [
            'https://www.caireinc.com/airsep/'
        ],
        'notes': 'Concentradores AirSep bajo CAIRE'
    },
    'Philips Respironics': {
        'models': [
            'REMstar', 'System One', 'EverFlo', 'SimplyGo', 'Millennium', 'NICO2'
        ],
        'sources': [
            'https://www.usa.philips.com/healthcare/resources/landing/respironics',
            'https://www.usa.philips.com/healthcare/product/HCNOCTN146/everflo-oxygen-concentrator'
        ],
        'notes': 'Incluye líneas REMstar/System One/EverFlo/SimplyGo/Millennium'
    },
    'ResMed': {
        'models': [
            'S7', 'S8', 'S9', 'AirSense 10', 'AirSense 11', 'VPAP 3', 'Astral 150'
        ],
        'sources': [
            'https://www.resmed.com/'
        ],
        'notes': 'Series Sx y AirSense'
    },
    'Nellcor': {
        'models': [
            'N-290', 'N-395', 'N-550', 'N-560', 'N-595', 'N-600', 'N-600X', 'NBP-295', 'NPB-195', 'NPB-290', 'NPB-4000'
        ],
        'sources': [
            'https://www.medtronic.com/covidien/en-us/products/pulse-oximetry.html'
        ],
        'notes': 'Oxímetros y monitores Nellcor de Medtronic'
    },
    'Fisher & Paykel Healthcare': {
        'models': [
            'HC100', 'HC150', 'HC221', 'MR410', 'MR428', 'MR700'
        ],
        'sources': [
            'https://www.fphcare.com/'
        ],
        'notes': 'Humidificadores y calentadores MR/HC'
    },
    'BMC': {
        'models': [
            'G1', 'G1 25T', 'G2', 'G2S', 'G3', 'RESmart', 'PolyWatch', 'PolyWatch YH-600B', 'MINI M1'
        ],
        'sources': [
            'https://global.bmc-medical.com/'
        ],
        'notes': 'CPAP/BiPAP series Gx y RESmart'
    },
    'Longfian': {
        'models': [
            'JAY-5', 'JAY-5Q', 'JAY-10', 'JAY-10D', 'JAY-120', 'JSB-1200'
        ],
        'sources': ['http://www.longfian.com/'],
        'notes': 'Concentradores JAY'
    },
    'Drive DeVilbiss Healthcare': {
        'models': [
            '515', '525', 'IntelliPAP', 'VacuAide 7305', 'VacuAide QSU 7314P-D'
        ],
        'sources': [
            'https://www.devilbisshealthcare.com/'
        ],
        'notes': 'Concentradores 5L/10L y VacuAide'
    },
    'Medix': {
        'models': [
            'OXI-3 PLUS', 'PC-305', 'PC-307'
        ],
        'sources': [],
        'notes': 'Modelos frecuentes en la base'
    },
    'Samtronic': {
        'models': [
            'ST-1000', 'ST-6000', 'ST-7000', 'ST-550 T2', 'ST-1000 SET'
        ],
        'sources': ['https://www.samtronic.com.br/'],
        'notes': 'Bombas de infusión'
    },
    'Newport': {
        'models': ['E-360', 'HT70'],
        'sources': ['https://www.medtronic.com/covidien/en-us/products/ventilation/newport-ht70-plus-ventilator.html'],
        'notes': 'Ventiladores Newport'
    },
    'Arcomed AG': {
        'models': ['Volumed', '5005'],
        'sources': ['https://www.arcomed.com/'],
        'notes': 'Bombas Volumed'
    },
    'Neumovent': {
        'models': ['GraphNet', 'Advance', 'TS'],
        'sources': ['https://www.tecmemedical.com/products/neumovent/'],
        'notes': 'Líneas GraphNet, Advance, TS de Neumovent (Tecme)'
    },
    'Marquette': {
        'models': ['Eagle', 'EAGLE 3000'],
        'sources': ['https://www.gehealthcare.com/'],
        'notes': 'Monitores/defibriladores Marquette'
    },
    'ZOLL': {
        'models': ['M-Series', 'E-Series'],
        'sources': ['https://www.zoll.com/'],
        'notes': 'Desfibriladores'
    },
    'HeartSine': {
        'models': ['samaritan'],
        'sources': ['https://heartsine.com/'],
        'notes': 'DEA samaritan'
    },
    'Covidien': {
        'models': ['Kangaroo', 'Kangaroo ePump', 'Kangaroo 224', 'Kangaroo 324', 'Kangaroo 924'],
        'sources': ['https://www.cardinalhealth.com/en/product-solutions/medical/enteral-feeding/enteral-feeding-pumps.html'],
        'notes': 'Bombas Kangaroo (hoy Cardinal Health)'
    },
    'Puritan Bennett': {
        'models': ['PB 560', 'GoodKnight'],
        'sources': ['https://www.medtronic.com/'],
        'notes': 'Ventiladores PB'
    },
    'Silfab': {
        'models': ['N-33A', 'N-33V', 'N-35A'],
        'sources': ['https://www.silfab.com.ar/'],
        'notes': 'Aspiradores y accesorios'
    },
}
