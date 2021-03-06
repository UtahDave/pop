# -*- coding: utf-8 -*-

# Import python libs
import os
import importlib
import inspect
import logging
import secrets
import sys

# Import pop libs
import pop.dirs
import pop.scanner
import pop.loader
import pop.exc
import pop.contract

EXT_SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)
log = logging.getLogger(__name__)


def ex_path(path):
    '''
    Take a path that is sent to the Sub and expand it if it is a string or not
    '''
    if path is None:
        return []
    elif isinstance(path, str):
        return path.split(',')
    elif isinstance(path, list):
        return path
    return []


class Hub:
    '''
    The redistributed pop central hub. All components of the system are
    rooted to the Hub.
    '''
    def __init__(self):
        self._subs = {}
        self._dynamic = {}
        self._dscan = False
        self._subs['pop'] = Sub(
                self,
                'pop',
                pypath='pop.mods.pop')
        self._iter_subs = sorted(self._subs.keys())
        self._iter_ind = 0

    def __getstate__(self):
        return dict(
            _subs=self._subs,
        )

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __iter__(self):
        def iter(subs):
            for sub in sorted(subs.keys()):
                yield subs[sub]
        return iter(self._subs)

    def _resolve_this(self, levels):
        '''
        This function allows for hub to pop introspective calls.
        This should only ever be called from within a hub module, otherwise
        it should stack trace, or return heaven knows what...
        '''
        if hasattr(sys, '_getframe'):  # implementation detail of CPython, speeds up things by 100x.
            desired_frame = sys._getframe(3)
            contracted = desired_frame.f_locals['self']
        else:
            call_frame = inspect.stack(0)[3]
            contracted = call_frame[0].f_locals['self']
        ref = contracted.ref.split('.')

        # (0=module, 1=module's parent etc.)
        level_offset = levels - 1
        traversed = self
        for i in range(len(ref) - level_offset):
            traversed = getattr(traversed, ref[i])
        return traversed

    def _remove_subsystem(self, subname):
        '''
        Remove the named subsystem
        '''
        if subname in self._subs:
            # Remove the subsystem
            self._subs.pop(subname)
            # reset the iterator
            self._iter_subs = sorted(self._subs.keys())
            self._iter_ind = 0
            return True
        return False

    def _scan_dynamic(self):
        '''
        Refresh the dynamic roots data used for loading app merge module roots
        '''
        self._dynamic = pop.dirs.dynamic_dirs()
        self._dscan = True

    def __getattr__(self, item):
        if item.startswith('_'):
            if item == item[0]*len(item):
                return self._resolve_this(len(item))
            else:
                return self.__getattribute__(item)
        if '.' in item:
            return self.pop.ref.last(item)
        if item in self._subs:
            return self._subs[item]
        return self.__getattribute__(item)


class Sub:
    '''
    The pop object contains the loaded module data
    '''
    def __init__(
            self,
            hub,
            subname,
            pypath=None,
            static=None,
            contracts_pypath=None,
            contracts_static=None,
            default_contracts=None,
            virtual=True,
            dyne_name=None,
            omit_start=('_'),
            omit_end=(),
            omit_func=False,
            omit_class=False,
            omit_vars=False,
            mod_basename='',
            stop_on_failures=False,
            init=True,
            is_contract=False,
            ):
        self._iter_ind = 0
        self._hub = hub
        self._subs = {}
        self._mem = {}
        self._subname = subname
        self._pypath = ex_path(pypath)
        self._static = ex_path(static)
        self._contracts_pypath = ex_path(contracts_pypath)
        self._contracts_static = ex_path(contracts_static)
        if isinstance(default_contracts, str):
            default_contracts = [default_contracts]
        self._default_contracts = default_contracts or ()
        self._dyne_name = dyne_name
        self._virtual = virtual
        self._omit_start = omit_start
        self._omit_end = omit_end
        self._omit_func = omit_func
        self._omit_class = omit_class
        self._omit_vars = omit_vars
        self._mod_basename = mod_basename
        self._stop_on_failures = stop_on_failures
        self._init = init
        self._is_contract = is_contract
        self._prepare()

    def _prepare(self):
        self._dirs = pop.dirs.dir_list(
            self._subname,
            'mods',
            self._pypath,
            self._static,
            )
        self._load_dyne()
        self._contract_dirs = pop.dirs.dir_list(
            self._subname,
            'contracts',
            self._contracts_pypath,
            self._contracts_static,
            )
        self._contract_dirs.extend(
            pop.dirs.inline_dirs(
                self._dirs,
                'contracts'
                )
            )
        if self._contract_dirs:
            self._contracts = Sub(
                self._hub,
                f'{self._subname}.contracts',
                static=self._contract_dirs,
                is_contract=True,
            )
        else:
            self._contracts = None
        self._name_root = self._load_name_root()
        self._mem = {}
        self._scan = pop.scanner.scan(self._dirs)
        self._loaded = {}
        self._vmap = {}
        self._load_errors = {}
        self._loaded_all = False

    def _load_dyne(self):
        '''
        Load up the dynamic dirs for this sub
        '''
        if not self._hub._dscan:
            self._hub._scan_dynamic()
        for path in self._hub._dynamic.get(self._dyne_name, []):
            self._dirs.append(path)

    def _load_name_root(self):
        '''
        Generate the root of the name to be used to apply to the loaded modules
        '''
        if self._pypath:
            return self._pypath[0]
        elif self._dirs:
            return secrets.token_hex()

    def __getstate__(self):
        return dict(
            _hub=self._hub,
            _subname=self._subname,
            _pypath=self._pypath,
            _static=self._static,
            _contracts_pypath=self._contracts_pypath,
            _contracts_static=self._contracts_static,
            _default_contracts=self._default_contracts,
            _virtual=self._virtual,
            _omit_start=self._omit_start,
            _omit_end=self._omit_end,
            _omit_func=self._omit_func,
            _omit_class=self._omit_class,
            _omit_vars=self._omit_vars,
            _mod_basename=self._mod_basename,
            _stop_on_failures=self._stop_on_failures,
            _init=self._init
        )

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._prepare()

    def __getattr__(self, item):
        '''
        If the item should be loaded, load it, else serve it
        '''
        if item.startswith('_'):
            return self.__getattribute__(item)
        if '.' in item:
            return self._hub.pop.ref.last(f'{self._subname}.{item}')
        if item in self._loaded:
            ret = self._loaded[item]
            # If this previously errored on load, try it again,
            # it might be ready to load now
            if isinstance(ret, pop.loader.LoadError):
                ret = self._find_mod(item)
                if isinstance(ret, pop.loader.LoadError):
                    # If this is still a LoadError, process it
                    self._process_load_error(ret)
            return ret
        elif item in self._subs:
            return self._subs[item]
        return self._find_mod(item)

    def __contains__(self, item):
        try:
            return hasattr(self, item)
        except pop.exc.PopLookupError:
            return False

    # @property
    # def __name__(self):
    #     return '{}.{}'.format(self._mod_basename, self._subname)

    def __iter__(self):
        self._load_all()
        def iter(loaded):
            for l in sorted(loaded.keys()):
                yield loaded[l]
        return iter(self._loaded)

    def __next__(self):
        self._load_all()
        if self._iter_ind == len(self._iter_keys):
            self._iter_ind = 0
            raise StopIteration
        self._iter_ind += 1
        return self._loaded[self._iter_keys[self._iter_ind - 1]]

    def _sub_init(self, init):
        '''
        Run load init.py for the sub, running '__init__' function if present
        '''
        if init:
            self._find_mod('init', match_only=True)

    def _process_load_error(self, mod, skip_full_stop=False):
        if not isinstance(mod, pop.loader.LoadError):
            # This is not a LoadError, return now!
            return False

        if mod.edict['verror']:
            error = '{0[msg]}: {0[verror]}'.format(mod())
            if skip_full_stop is False and self._stop_on_failures is True:
                raise pop.exc.PopError(error)
            log.info(error)
            return
        error = '{0[msg]}: {0[exception]!r}'.format(mod())
        if mod.traceback:
            error += '\n' + mod.traceback
        if skip_full_stop is False and self._stop_on_failures is True:
            raise pop.exc.PopError(error)
        if mod.traceback:
            log.warning(error)
        else:
            log.info(error)
        return True

    def _find_mod(self, item, match_only=False):
        '''
        find the module named item
        '''
        for iface in self._scan:
            for bname in self._scan[iface]:
                if os.path.basename(bname) == item:
                    self._load_item(iface, bname)
            if item in self._loaded:
                return self._loaded[item]
        if not match_only:
            for iface in self._scan:
                for bname in self._scan[iface]:
                    if self._scan[iface][bname].get('loaded'):
                        continue
                    self._load_item(iface, bname)
                    if item in self._loaded:
                        return self._loaded[item]
        # Let's see if the module being lookup is in the load errors dictionary
        if item in self._load_errors:
            # Return the LoadError
            return self._load_errors[item]

    def _load_item(self, iface, bname):
        '''
        Load the named basename
        '''
        if iface not in self._scan:
            raise pop.exc.PopLoadError('Bad call to load item, no iface {}'.format(iface))
        if bname not in self._scan[iface]:
            raise pop.exc.PopLoadError(
                'Bad call to load item, no bname {} in iface {}'.format(bname, iface))
        mname = '{}.{}'.format(self._name_root, os.path.basename(bname))
        mod = pop.loader.load_mod(
                mname,
                iface,
                self._scan[iface][bname]['path'],
        )
        if self._process_load_error(mod):
            self._load_errors[os.path.basename(bname)] = mod
            return
        self._prep_mod(mod, iface, bname)

    def _prep_mod(self, mod, iface, bname):
        '''
        Prepare the module!
        '''
        vret = pop.loader.load_virtual(
                self._hub,
                self._virtual,
                mod,
                bname)
        if 'error' in vret:
            # Virtual Errors should not full stop pop
            self._process_load_error(vret['error'], skip_full_stop=True)
            # Store the LoadError under the __virtualname__ if defined
            self._load_errors[vret['vname']] = vret['error']
            return

        contracts = pop.contract.load_contract(
                self._contracts,
                self._default_contracts,
                mod,
                vret['name'])
        name = vret['name']
        if name.endswith(EXT_SUFFIXES):
            for ext in EXT_SUFFIXES:
                if name.endswith(ext):
                    name = name.split(ext)[0]
                    break
        mod_dict = pop.loader.prep_loaded_mod(
                self,
                mod,
                name,
                contracts)
        if name != 'init':
            pop.verify.contract(self._hub, contracts, mod_dict)
        self._loaded[name] = mod_dict
        self._vmap[mod.__file__] = name
        # Let's mark the module as loaded
        self._scan[iface][bname]['loaded'] = True
        # Now that the module has been added to the sub, call mod_init
        pop.loader.mod_init(self._hub, mod)

    def _load_all(self):
        '''
        Load all modules found during the scan.

        .. attention:: This completely disables the lazy loader behavior or pop
        '''
        if self._loaded_all is True:
            return
        for iface in self._scan:
            for bname in self._scan[iface]:
                if self._scan[iface][bname].get('loaded'):
                    continue
                self._load_item(iface, bname)
        self._loaded_all = True
