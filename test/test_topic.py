from app.topics.topic_intelligence import topic_intelligence

samples = [

    "Today we are learning Microcontrollers.",

    "CPU",

    "RAM",

    "Flash Memory",

    "GPIO",

    "UART SPI I2C",

    "Now we study ARM Cortex M4.",

    "NVIC",

    "CMSIS",

    "SysTick",

]

for sentence in samples:

    print("-"*60)

    print(sentence)

    if topic_intelligence.process(sentence):

        print("NEW TOPIC")

    else:

        print("UPDATE CURRENT SLIDE")