from jedi.inference.cache import infer_state_function_cache


@infer_state_function_cache()
def get_yield_exprs(infer_state, funcdef):
    return list(funcdef.iter_yield_exprs())
