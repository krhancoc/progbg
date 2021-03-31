`progbg`
========
The **Prog**rammable **B**enchmarker and **G**raphing Tool

**The problem:**
Identifying bottlenecks and problems within a system is essential when developing larger systems. Being
able to quickly produce simple graphs helps see these bottlenecks more clearly as well as possibly see degenerative issues within a system.
`progbg` is a simple framework that exposes a planning API to allow you to plan execution of
your benchmarks through the registering of workloads and backends. Data produced by these classes are parsed to produce data that can be used by graphs and figures. 
`progbg` utilizes [`matplotlib`](https://matplotlib.org) for its graphing library.

More information and docs can be found [here](https://krhancoc.github.io/progbg/)

Installation
------------
`progbg` can be installed through pip

```sh
$ pip install progbg
```

Example
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
