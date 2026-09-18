# Makefile

# Compiler
CXX = g++

# Compiler flags
CXXFLAGS = -Wall -Wextra -std=c++11

# Source files
SRCS = test.cpp mymethod.cpp

# Header files
HEADERS = mymethod.h

# Object files
OBJS = $(SRCS:.cpp=.o)

# Executable name
TARGET = test

# Default target
all: $(TARGET)

# Rule to build the executable
$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -g -o $@ $^

# Rule to build object files from source files
%.o: %.cpp $(HEADERS)
	$(CXX) $(CXXFLAGS) -c -o $@ $<

# Clean target
clean:
	rm -f $(OBJS) $(TARGET)

