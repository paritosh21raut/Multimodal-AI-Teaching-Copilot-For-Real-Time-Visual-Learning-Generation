from app.lecture.context_buffer import context_buffer

context_buffer.add("Today we are learning Microcontrollers.")
context_buffer.add("CPU")
context_buffer.add("RAM")
context_buffer.add("Flash Memory")
context_buffer.add("GPIO")

print("Buffer Size:", context_buffer.size())
print()
print(context_buffer.get_context())