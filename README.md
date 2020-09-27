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
The API is developed to allow not just basic option paramaters to modify graphs and benchmarks,  but also defining
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
Firsty we should define the following terms:

1. **Executions** are composed of:
  * **Backends**: The system you are trying to test
  * **Benchmark**: An application that runs on a backend and produces data output
  * **Parsers**: Parsers that consumes data to produce objects which graphs can consume
2. **Figures** take formatting information (styles etc.) and are composed of:
  * **Graphs**: Consume parser information and formatting information, to help create figures

Simply put you define benchmarks and backends with the provided decorators 
`registerbackend` and `registerbenchmark` these wrap CLASSES. 

Sample Backend would look like:
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
Backends require both the init and uninit methods, these are what are ran before 
benchmarks are executed.

A sample benchmark would look like the following:
```python
@sb.registerbenchmark
class WRK:
    @staticmethod
    def run(outfile, test = 5, x = 10):
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
This is just a dummy benchmark that randomly produces 3 numbers.

Now that the backends and benchmark is defined, we can use these to define executions.

A simple execution:

```python
sb.plan_execution("my_execution",
        sb.DefBenchmark("wrk",
            sb.Variables(
                consts = {
                    "test" : 2
                },
                var = [("x" ,range(0, 3, 1))]
            ),
            iterations = 5,
            out_dir = "out",
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
        parse = sb.MatchParser("out",
            {
                "^Latency": (
                    ["avg", "max", "min"], func
                )
            },
            save = "out"
        )
)
```

# Planning Executions
`plan_execution` takes in four arguments:

**A unique name**

This is a name that will be used by the grapher to help create figures. So it must be unique.

**A Benchmark object**

Currently there is only one - `DefBenchmark`. This benchmark
required 3 parameters, its variable list, number of iterations that you'd this benchmark
to run, as well as a directory to push raw data to.

### Variables Objects
These objects define want changes and stays constant.  They are used within both defining
variables for the backend as well as the benchmark.  This allows progbg to essentially
iterate through the cross product of all changing variables defined within the 
backend and the benchmark. For our specific example we are changing the variable
"x" and keeping "test" constant.  These variables are the arguments to the benchmark registered above!

The same goes for the variables outline within the backend definitions (explained ahead).

**A Dictionary that describes the backends**

These are the backends you wish to run.  Notice the format to describe them.  When we register
backends we can refer back to them using their lower case name, and we are also able
to compose these backends. 

"ffs/bck" uses a composition of both the FFS defined backend and BCK backend (found above).
This inits the backend in the order of the path.  With the benchmark being ran after all defined
backends have been inited. This allows you to, like in the psuedo example above, create a 
fast file system backend, then place some server (tomcat, or whatever you need) on top
then run the benchmark.

Note that backends are created and destroyed after EVERY benchmark. An option will be 

**A Parser Object**

This takes the output from your executions and parses it to a usable format.  Currently
there is only one supported parser.

### Match Parser
The Match parser take a dictionary of regex strings to a tuple of a list of named outputs
and a function that create those outputs. When the parser receives raw data it goes through
line by line, and passes the line to the function if the regex search is true on that line.

For our above example this is matching on the regex "^Latency" and outputing our variables
avg, max, and min.  These can be used by the graph tool to be graphed.

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

Currently there are two objects `LineGraph` and `BarGraph`.  Refer to docs for more 
detailed usage.  But in general, these graphs take the variables that you wish to graph
by there name (these are names that we provided either to the variables for the backend, the benchmarks,
or the parser).

In our above example we are plotting how "avg" changes over "x", and we want the variables
`pass_me_in`, `aother_var`, `test` to be fixed at specific points.  We then wish this graph to
be outputed to `avg.svg`.

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
2. Command line Benchmark Class
3. Better Error Handling and Hints
4. Tests
5. Disable re-initing backends
