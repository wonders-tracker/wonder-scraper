from pydoll.browser import Chrome
import inspect

print("Chrome methods:")
for name, member in inspect.getmembers(Chrome):
    if not name.startswith("_"):
        print(name)

print("\nInit signature:")
print(inspect.signature(Chrome.__init__))

