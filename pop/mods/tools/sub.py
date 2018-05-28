# -*- coding: utf-8 -*-
'''
Control and add subsystems to the running daemon hub
'''
# Import python libs
import os
# Import pop libs
import pop.hub


def add(hub,
        modname,
        sub=None,
        subname=None,
        pypath=None,
        static=None,
        contracts_pypath=None,
        contracts_static=None,
        default_contracts=None,
        virtual=True,
        omit_start=('_'),
        omit_end=(),
        omit_func=False,
        omit_class=True,
        omit_vars=False,
        mod_basename='pop.sub',
        stop_on_failures=False,
        init=None,
        ):
    '''
    Add a new subsystem to the hub
    '''
    # Make sure that unintended funcs are not called with the init
    if init is True:
        init = 'init.new'
    subname = subname if subname else modname
    if sub:
        root = sub
    else:
        root = hub
    root._subs[modname] = pop.hub.Sub(
            hub,
            modname,
            subname,
            pypath,
            static,
            contracts_pypath,
            contracts_static,
            default_contracts,
            virtual,
            omit_start,
            omit_end,
            omit_func,
            omit_class,
            omit_vars,
            mod_basename,
            stop_on_failures)
    root._subs[modname]._pop_init(init)
    root._iter_subs = sorted(root._subs.keys())


def remove(hub, subname):
    '''
    Remove a pop from the hub, run the shutdown if needed
    '''
    if hasattr(hub, subname):
        sub = getattr(hub, subname)
        if hasattr(sub, 'init'):
            mod = getattr(sub, 'init')
            if hasattr(mod, 'shutdown'):
                mod.shutdown()
        hub._remove_subsystem(subname)


def load_all(hub, subname):
    '''
    Load al modules under a given pop
    '''
    if hasattr(hub, subname):
        sub = getattr(hub, subname)
        sub._load_all()
        return True
    else:
        return False


def get_dirs(hub, sub):
    '''
    Return a list of directories that contain the modules for this subname
    '''
    return sub._dirs


def iter_subs(hub, sub):
    '''
    Return an iterator that will traverse just the subs. This is useful for
    nested subs
    '''
    for name in sorted(sub._subs):
        yield sub._subs[name]


def load_subdirs(hub, sub):
    '''
    Given a sub, load all subdirectories found under the sub into a lower namespace
    '''
    dirs = hub.tools.sub.get_dirs(sub)
    for dir_ in dirs:
        for fn in os.listdir(dir_):
            if fn.startswith('_'):
                continue
            full = os.path.join(dir_, fn)
            if os.path.isdir(full):
                # Load er up!
                hub.tools.sub.add(
                        fn,
                        sub=sub,
                        static=[full],
                        virtual=sub._virtual,
                        omit_start=sub._omit_start,
                        omit_end=sub._omit_end,
                        omit_func=sub._omit_func,
                        omit_class=sub._omit_class,
                        omit_vars=sub._omit_vars,
                        mod_basename=sub._mod_basename,
                        stop_on_failures=sub._stop_on_failures)
