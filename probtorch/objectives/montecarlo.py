from numbers import Number
from torch.nn.functional import softmax


def elbo(q, p, sample_dim=None, batch_dim=None, alpha=0.1, beta=1.0):
    r"""Calculates an importance sampling estimate of the semi-supervised
    evidence lower bound (ELBO), as described in [1]

    .. math::
       E_{q(z | x, y)} \left[ \log p(x | y, z) \right]
       - \beta E_{q(z | x, y)} \left[ \log \frac{q(y,z | x)}{p(y,z)} \right]
       + (\beta + \alpha) E_{q(z | x)}\left[ \log \frac{q(y, z| x)}{q(z | x)} \right]

    The sets of variables :math:`x`, :math:`y` and :math:`z` refer to:

        :math:`x`: The set of conditioned nodes that are present in `p` but
        are not present in `q`.

        :math:`y`: The set of conditioned nodes in `q`, which may or may
        not also be present in `q`.

        :math:`z`: The set of sampled nodes present in both `q` and `p`.

    Importance sampling is used to approximate the expectation over
    :math:`q(z| x,y)`.

    Arguments:
        q(:obj:`Trace`): The encoder trace.

        p(:obj:`Trace`): The decoder trace.

        sample_dim(int, optional): The dimension containing individual samples.

        batch_dim(int, optional): The dimension containing batch items.

        alpha(float, default 0.1): Coefficient for the ML term.

        beta(float, default 1.0):  Coefficient for the KL term.

    References:
        [1] Siddharth Narayanaswamy, Brooks Paige, Jan-Willem van de Meent,
        Alban Desmaison, Frank Wood, Noah D Goodman, Pushmeet Kohli, and
        Philip HS Torr, Semi-Supervised Learning of Disentangled
        Representations, NIPS 2017.
    """
    log_weights = q.log_joint(sample_dim, batch_dim, q.conditioned())
    return (log_like(q, p, sample_dim, batch_dim, log_weights) -
            beta * kl(q, p, sample_dim, batch_dim, log_weights) +
            (beta + alpha) * ml(q, sample_dim, batch_dim, log_weights))


def log_like(q, p, sample_dim=None, batch_dim=None, log_weights=None):
    r"""Computes a Monte Carlo estimate of the log-likelihood.

    .. math::
       E_{q(z | x, y)}[\log p(x | y, z)]
       \simeq \frac{1}{S} \frac{1}{B} \sum_{s=1}^S \sum_{b=1}^B
              \log p(x^{(b)} | z^{(s,b)}, y^{(b)})

    The sets of variables :math:`x`, :math:`y` and :math:`z` refer to:

        :math:`x`: The set of conditioned nodes that are present in `p` but
        are not present in `q`.

        :math:`y`: The set of conditioned nodes in `q`, which may or may
        not also be present in `q`.

        :math:`z`: The set of sampled nodes present in both `q` and `p`.

    Importance sampling is used to approximate the expectation over
    :math:`q(z| x,y)`.

    Arguments:
        q(:obj:`Trace`): The encoder trace.

        p(:obj:`Trace`): The decoder trace.

        sample_dim(int, optional): The dimension containing individual samples.

        batch_dim(int, optional): The dimension containing batch items.

        log_weights(:obj:`Variable` or number, optional): Log weights for
        samples. Calculated when not specified.
    """
    x = [n for n in p.conditioned() if n not in q]
    log_px = p.log_joint(sample_dim, batch_dim, x)
    if sample_dim is None:
        return log_px.mean()
    else:
        if log_weights is None:
            log_weights = q.log_joint(sample_dim, batch_dim, q.conditioned())
        if isinstance(log_weights, Number):
            return log_px.mean()
        else:
            weights = softmax(log_weights, 0)
            return (weights * log_px).sum(0).mean()


def kl(q, p, sample_dim=None, batch_dim=None, log_weights=None):
    r"""Computes a Monte Carlo estimate of the unnormalized KL divergence
    described in [1].

    .. math::
       E_{q(z | x, y)}\left[ \log \frac{q(y, z | x)}{p(y, z)} \right]
       \simeq
       \frac{1}{S} \frac{1}{B} \sum_{s=1}^S \sum_{b=1}^B
       \left[ \log \frac{q(y^{(b)}, z^{(s,b)} | x^{(b)})}
                        {p(y^{(b)}, z^{(s,b)})} \right]

    The sets of variables :math:`x`, :math:`y` and :math:`z` refer to:

        :math:`x`: The set of conditioned nodes that are present in `p` but
        are not present in `q`.

        :math:`y`: The set of conditioned nodes in `q`, which may or may
        not also be present in `q`.

        :math:`z`: The set of sampled nodes present in both `q` and `p`.

    Importance sampling is used to approximate the expectation over
    :math:`q(z| x,y)`.

    Arguments:
        q(:obj:`Trace`): The encoder trace.

        p(:obj:`Trace`): The decoder trace.

        sample_dim(int, optional): The dimension containing individual samples.

        batch_dim(int, optional): The dimension containing batch items.

        log_weights(:obj:`Variable` or number, optional): Log weights for
            samples. Calculated when not specified.

    References:
        [1] Siddharth Narayanaswamy, Brooks Paige, Jan-Willem van de Meent,
        Alban Desmaison, Frank Wood, Noah D Goodman, Pushmeet Kohli, and
        Philip HS Torr, Semi-Supervised Learning of Disentangled
        Representations, NIPS 2017.
    """
    y = q.conditioned()
    z = [n for n in q.sampled() if n in p]
    if log_weights is None:
        log_qy = q.log_joint(sample_dim, batch_dim, y)
    else:
        log_qy = log_weights
    log_py = p.log_joint(sample_dim, batch_dim, y)
    log_pz = p.log_joint(sample_dim, batch_dim, z)
    log_qz = q.log_joint(sample_dim, batch_dim, z)
    log_qp = (log_qy + log_qz - log_py - log_pz)
    if sample_dim is None:
        return log_qp.mean()
    else:
        if isinstance(log_weights, Number):
            return log_qp.mean()
        else:
            weights = softmax(log_weights, 0)
            return (weights * log_qp).sum(0).mean()


def ml(q, sample_dim=None, batch_dim=None, log_weights=None):
    r"""Computes a Monte Carlo estimate of maximum likelihood encoder objective

    .. math::
       E_{q(z | x)}\left[ \log \frac{q(y, z| x)}{q(z | x)} \right]
       \simeq \frac{1}{S} \frac{1}{B} \sum_{s=1}^S \sum_{b=1}^B
       \left[ \log \frac{q( y^{(b)}, z^{(s,b)} | x^{(b)})}
                        {q(z^{(s,b)} | x^{(b)})} \right]

    The sets of variables :math:`x`, :math:`y` and :math:`z` refer to:

        :math:`x`: The set of conditioned nodes that are present in `p` but
        are not present in `q`.

        :math:`y`: The set of conditioned nodes in `q`, which may or may
        not also be present in `q`.

        :math:`z`: The set of sampled nodes present in both `q` and `p`.

    Arguments:
        q(:obj:`Trace`): The encoder trace.

        p(:obj:`Trace`): The decoder trace.

        sample_dim(int, optional): The dimension containing individual samples.

        batch_dim(int, optional): The dimension containing batch items.

        log_weights(:obj:`Variable` or number, optional): Log weights
        for samples. Calculated when not specified.
    """
    if log_weights is None:
        log_qy = q.log_joint(sample_dim, batch_dim, q.conditioned())
    else:
        log_qy = log_weights
    if isinstance(log_qy, Number):
        return log_qy
    else:
        return log_qy.mean()
