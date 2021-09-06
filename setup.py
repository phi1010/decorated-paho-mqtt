import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
setuptools.setup(
    name='decorated_paho_mqtt',
    version='1.0.5',
    url='https://github.com/phi1010/decorated-paho-mqtt',
    author='Phillip Kuhrt',
    author_email='mail@phi1010.com',
    description='Wrapper for Paho MQTT with declarative subscriptions and topic parsing utilities',
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    install_requires=[
        'paho-mqtt',
    ],
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.7",
)

