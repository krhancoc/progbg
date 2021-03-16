`progbg`
========
The **Prog**rammable **B**enchmarker and **G**raphing Tool

**The problem:**
I have to benchmark my system.  I want to evaluate its success by using specialized benchmarks that run
using it or on top of it. These workloads generate data which needs to be parsed into a usable, analyzable form.
I then would like to generate figures to firstly to better see trends in my data as well as present findings to others.

**Solution:**
`progbg` is a simple glue framework that exposes a planning API to allow you to plan and program
your benchmarks, parsing, and finally the graphs and figures that are produced by them. 
The API is developed to allow not just basic option parameters to modify graphs and benchmarks,  but also defining
and changing behaviour through defined functions and classes that have access to [`matplotlib`](https://matplotlib.org)
which `progbg` uses for its graphing library.

Installation
------------
`progbg` can be installed through pip

```sh
$ pip install progbg
```

Quick Start
-----------
Let's define the following terms:

1. **Executions** are composed of backends and a benchmark. They form the **running** component of progbg
2. **Backend**: The system underlying system you may be trying to test.  This is setup prior to running a benchmark.  Benchmarks
can be composed using path style syntax (See below for an example).
3. **Benchmark**: An application that runs on a backend and produces data output, using a given parser.
4. **Parser**: Parsers that consume data to produce objects which graphs use.
5. **Graph**: Consume parser information and formatting information, to help output individual graphs.  Can be used by themselves
or be used by figures.
6. **Figure** take formatting information (styles etc.) and are composed of graphs.


Backends and benchmarks are defined with the provided decorators 
`registerbackend` and `registerbenchmark`. These decorators wrap classes. 

A sample backend would look like:
```python
@sb.registerbackend
class FFS:
    @staticmethod
    # You can use whatever names for arguments you'd like but arguments should be
    # a unique name
    def init(myvar = 10, pass_me_in = 5):
        print("FFS Backend initing {} {}".format(myvar, pass_me_in))

    @staticmethod
    def uninit():
        pass

# Another backend as well
@sb.registerbackend
class BCK:
    @staticmethod
    def init(another_var = 5):
        print("ANOTER Backend initing {} ".format(another_var))

    @staticmethod
    def uninit():
        pass

```
Backends require both the init and uninit methods, which are run before 
benchmarks are executed.

A sample benchmark would look like the following:
```python
@sb.registerbenchmark
class WRK:
    @staticmethod
    def run(backend, outfile, test = 5, x = 10):
        # DO STUFF
        avg = str(randint(1, 1000))
        max = str(randint(500, 1000))
        min = str(randint(1, 499))
        vals="{} {}\n".format(test, x)
        strn="Latency  {}  {}  {}".format(avg, max, min)
        with open(outfile, 'w') as out:
            out.write(vals)
            out.write(strn)
```
This is a dummy benchmark that randomly produces 3 numbers.

Note: 
1. Benchmarks require at least one argument which is the path to an output file, which the benchmark
should use to pipe output related to the data from the benchmark.  <!-- "If a benchmark does not use that." -This sentence fragment was sitting here. I'm assuming it 's supposed to tell you what happens if an output is missing'--> This can be seen as the path for the -o argument
many benchmarks use. I suggest using subprocess and piping the output to the file.
2. All variable names used for arguments within methods for backends or benchmarks require a name, and to be unique within the scope
of the entire file. For example above, the `WRK` benchmark and `FFS` backend cannot both have a variable named `test`.


An execution is composed of backends and benchmarks.

A simple execution:

```python
sb.plan_execution("my_execution",
        # Notice the "wrk" - this is to identify which registered benchmark to use (specified above)
        sb.DefBenchmark("wrk",
            sb.Variables(
                consts = {
                    "test" : 2
                },
                var = [("x" ,range(0, 3, 1))]
            ),
            iterations = 5,
            parse = sb.MatchParser(
            {
                "^Latency": (
                    ["avg", "max", "min"], func
                )
            },
        )
        ),
        {
            # Note: The arguments passed in here have the same name as the arguments used
            # for registered benchmark
            'ffs/bck': sb.Variables(
                consts = {
                    "myvar": 5
                },
                var = [("pass_me_in", range(0, 10, 2))]
            ),
            'bck': sb.Variables(
                consts = {},
                var = [("another_var", [1, 5 ,7])]
            )
        },
        out = "out.db"
)
```
# Planning Executions
`plan_execution` takes in 3 arguments:

**A unique name**

This is a name that will be used by graph objects te help create graphs. It is used to identify the execution and
all data produced by it.

**A Benchmark object**

Currently there is only one - `DefBenchmark`. This benchmark
required 4 parameters, the lowercase name of the registered class, its Variable objects, number of iterations that you'd this benchmark
to run, and the parser that will convert data from the benchmark to usable objects.

**Output string**
Currently there are two supported outputs for benchmarks.  If the user supplies a name
with a ".db" extension, then data will be placed into a sqlite3 database. Multiple
executions can share this database.

Any other name will be seen as a directory and each benchmark run will be stored as a seperate
file.

### Variables Objects
These objects define what changes and stays constant during the execution run.
They are used within both defining variables for the backend as well as the
benchmark.  This allows progbg to iterate through the cross product of all
changing variables defined within the backend and the benchmark. For our
benchmark we are changing the variable "x" and keeping "test" constant. The
given backends are also changing their own variables. These variable names are
the arguments to the benchmark and backend registered above.

**A Dictionary that describes the backends**

These are the backends you wish to run.  Notice the format to describe them.  When we register
backends we can refer back to them using their lower case name, and we are also able
to compose these backends. 

"ffs/bck" uses a composition of both the FFS defined backend and BCK backend (found above).
This inits the backend in the order of the path.  With the benchmark being run after all defined
backends init function have been called. This for example allows you to create a 
fast file system backend, then place some server (tomcat, or whatever you need) on top
then run the composed benchmark.

Note that backends are created and destroyed after EVERY benchmark, this can be disabled with the `--no-reinit` flag.

### Match Parser
The Match parser takes a dictionary of regex strings to a tuple of named outputs
and a function that creates those outputs. When the parser receives raw data it goes through
line by line, and passes the line to the provided function if the regex search is true on that line

For our above example this is matching on the regex "^Latency" and outputing our variables
avg, max, and min.  These can be used by the graph tool to be graphed. The names must also be unique globally.

# Planning Graphs

Finally we would like to produce a graph (or many) from our executions. 
```python
sb.plan_graph("graph-1",
    sb.LineGraph(
        "x",
        "avg",
        ["my_execution:ffs/bck"],
        {
            "pass_me_in": 4,
            "another_var": 5,
            "test" : 2,
        },
        out = "avg.svg"
    ),
)
```
We use the `plan_graph` function, which takes 2 arguments:

**Unique Name**

This name is used so that we can plan figures if we so desire with these graphs

**Graph Object**

Currently there are two graph styles (`LineGraph` and `BarGraph`).  Refer to docs for more 
detailed usage.  But in general, these graphs take the variables that you wish to graph
by their name (these are names that were provided either to the variables for the backend, the benchmarks,
or the parser), and uses this to grab the appropriate data from the specified saved output (either the directory.
or sql database).

In our above example we are plotting how "avg" changes over "x", and we want the variables
`pass_me_in`, `aother_var`, `test` to be fixed at specific points.  We then wish this graph to
be outputed to `avg.svg`. The graph will always output an svg by default (for use within the
flask server that can be used to present graphs).  

`progbg` also supports `.pgf` extensions


More
---------------
Take a look at a working [example](tests/plan.py) plan.  Try running it with the command
`progbg plan.py -p 8080` and go to `localhost:8080` to view the example graphs!

Viewing Graphs
------------
Graphs are saved by default in the `graphs` directory of the current working directory.

By passing the argument `-p PORT` to `progbe`, this will expose figures and graphs to be viewed by your browser
at `http://localhost:PORT`

Author
------
Kenneth R Hancock `krhancoc <https://github.com/krhancoc>`

TODO
----
1. CSV Parser
2. Command line Benchmark Class (We may also not even need this, we may only need one benchmark class)
3. Better Error Handling and Hints
4. Tests
