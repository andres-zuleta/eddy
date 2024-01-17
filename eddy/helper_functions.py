from pyexpat.errors import XML_ERROR_PARAM_ENTITY_REF
from mpl_toolkits.axes_grid1.axes_divider import make_axes_locatable
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import numpy as np

# -- MCMC / OPTIMIZATION FUNCTIONS -- #

def random_p0(p0, scatter, nwalkers):
    """
    Introduce scatter to starting positions while allowing for starting
    positions scattered about zero.

    Args:
        p0 (list): Starting positions.
        scatter (float): Scatter to apply to the starting positions.
        nwalkers (int): Number of walkers.

    Returns:
        p0 (ndarray): A (nwalkers, ndim) shaped array of starting positions.
    """
    p0 = np.atleast_1d(np.squeeze(p0))
    dp0 = np.random.randn(nwalkers * len(p0)).reshape(nwalkers, len(p0))
    dp0 = np.where(p0 == 0.0, 1.0, p0)[None, :] * (1.0 + scatter * dp0)
    return np.where(p0[None, :] == 0.0, dp0 - 1.0, dp0)


def _errors(x, dy, return_uncertainty):
    """
    Parse the inputs related to errors for use with scipy.optimize.curve_fit.

    Args:
        x (array): Dependent variable.
        dy (array): Uncertainty.
        return_uncertainty (bool): Whether to return the uncertainty.

    Returns:
        dy (array), return_uncertainty (bool), absolute_sigma (bool): Values
            needed for scipy.optimize.curve_fit.

    """
    if return_uncertainty is None:
        return_uncertainty = dy is not None
    dy = np.ones(x.size) * (1.0 if dy is None else dy)
    if np.all(np.isnan(dy)):
        dy = np.ones(x.size)
        absolute_sigma = False
    else:
        absolute_sigma = True
    return dy, return_uncertainty, absolute_sigma


def fit_gaussian(x, y, dy=None, return_uncertainty=None):
    """
    Fit a Gaussian form to (x, y[, dy]).

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.

    Returns:
        popt (array)[, cvar(array)]: The best fit parameters and, optionally,
        the uncertainty on those parameters.
    """
    dy, return_uncertainty, absolute_sigma = _errors(x, dy, return_uncertainty)
    p0 = get_p0_gaussian(x, y)
    try:
        popt, cvar = curve_fit(gaussian, x, y, sigma=dy, p0=p0,
                               absolute_sigma=absolute_sigma,
                               maxfev=100000)
        cvar = np.diag(cvar)**0.5
    except Exception:
        popt = [np.nan, np.nan, np.nan]
        cvar = popt.copy()
    return (popt, cvar) if return_uncertainty else popt


def fit_gaussian_thick(x, y, dy=None, return_uncertainty=None):
    """
    Fit an optically thick Gaussian function to (x, y[, dy]).

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.

    Returns:
        popt (array)[, cvar(array)]: The best fit parameters and, optionally,
        the uncertainty on those parameters.
    """
    dy, return_uncertainty, absolute_sigma = _errors(x, dy, return_uncertainty)
    p0 = fit_gaussian(x=x, y=y, dy=dy,
                      return_uncertainty=False)
    p0 = np.append(p0, 0.5)
    try:
        popt, cvar = curve_fit(gaussian_thick, x, y, sigma=dy, p0=p0,
                               absolute_sigma=absolute_sigma,
                               maxfev=100000)
        cvar = np.diag(cvar)**0.5
    except Exception:
        popt = [np.nan, np.nan, np.nan, np.nan]
        cvar = popt.copy()
    return (popt, cvar) if return_uncertainty else popt


def fit_double_gaussian(x, y, dy=None, return_uncertainty=None):
    """
    Fit two Gaussian lines to (x, y[, dy]) where the maximum of the two
    Gaussians is used as the model.

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.

    Returns:
        popt (array)[, cvar(array)]: The best fit parameters and, optionally,
        the uncertainty on those parameters.
    """

    # Defaults.

    dy, return_uncertainty, absolute_sigma = _errors(x, dy, return_uncertainty)
    popt = [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]
    cvar = popt.copy()

    # Initial single Gaussian fit.

    popt_a, cvar_a = fit_gaussian(x=x, y=y, dy=dy, return_uncertainty=True)
    if not all(np.isfinite(popt_a)):
        return (popt, cvar) if return_uncertainty else popt

    # Double Gaussian fit. Try first a fit where the profile is a sum of two
    # components, then use this as strong priors for a max of two component
    # fit. This is because the max version is hard to optimize.

    p0 = [popt_a[0] + popt_a[1], popt_a[1], 0.8 * popt_a[2],
          popt_a[0] - popt_a[1], popt_a[1], 0.8 * popt_a[2]]
    try:
        popt_b, _ = curve_fit(double_gaussian_sum, x, y, sigma=dy, p0=p0,
                                   absolute_sigma=absolute_sigma,
                                   maxfev=100000)
        p0 = [popt_b[0], popt_b[1], double_gaussian_sum(popt_b[0], *popt_b),
              popt_b[3], popt_b[4], double_gaussian_sum(popt_b[3], *popt_b)]
        popt_b, cvar_b = curve_fit(double_gaussian_max, x, y, sigma=dy, p0=p0,
                                   absolute_sigma=absolute_sigma,
                                   maxfev=100000)
        cvar_b = np.diag(cvar_b)**0.5
        if popt_b[5] > popt_b[2]:
            popt_b = np.append(popt_b[3:], popt_b[:-3])
    except Exception:
        return (popt, cvar) if return_uncertainty else popt
    return (popt_b, cvar_b) if return_uncertainty else popt_b


def fit_double_gaussian_fixeddV(x, y, dy=None, return_uncertainty=None):
    """
    Same as the `fit_double_gaussian` function, but where the lines share a
    width.

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.

    Returns:
        popt (array)[, cvar(array)]: The best fit parameters and, optionally,
        the uncertainty on those parameters.
    """

    # Defaults.

    dy, return_uncertainty, absolute_sigma = _errors(x, dy, return_uncertainty)
    popt = [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan]
    cvar = popt.copy()

    # Initial single Gaussian fit.

    popt_a, _ = fit_gaussian(x=x, y=y, dy=dy, return_uncertainty=True)
    if not all(np.isfinite(popt_a)):
        return (popt, cvar) if return_uncertainty else popt

    # Double Gaussian fit. Try first a fit where the profile is a sum of two
    # components, then use this as strong priors for a max of two component
    # fit. This is because the max version is hard to optimize.

    p0 = [popt_a[0] + popt_a[1], popt_a[1], 0.8 * popt_a[2],
          popt_a[0] - popt_a[1], 0.8 * popt_a[2]]
    try:
        popt_b, _ = curve_fit(double_gaussian_sum_fixeddV, x, y, sigma=dy,
                              p0=p0, absolute_sigma=absolute_sigma,
                              maxfev=100000)
        p0 = [popt_b[0], popt_b[1],
              double_gaussian_sum_fixeddV(popt_b[0], *popt_b),
              popt_b[3],
              double_gaussian_sum_fixeddV(popt_b[3], *popt_b)]
        popt_b, cvar_b = curve_fit(double_gaussian_max_fixeddV, x, y, sigma=dy,
                                   p0=p0, absolute_sigma=absolute_sigma,
                                   maxfev=100000)
        cvar_b = np.diag(cvar_b)**0.5
        if popt_b[4] > popt_b[2]:
            popt_b = [popt_b[3], popt_b[1], popt_b[4], popt_b[0], popt_b[2]]
            popt_b = np.squeeze(popt_b)
    except Exception:
        return (popt, cvar) if return_uncertainty else popt
    return (popt_b, cvar_b) if return_uncertainty else popt_b


def get_gaussian_center(x, y, dy=None, return_uncertainty=None, fill=1e50):
    """
    Return the line center from a Gaussian fit to the spectrum.

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.
        fill (Optional[float]): Values to return if the fit fails.

    Returns:
        popt (array)[, cvar(array)]: The best fit line center and, optionally,
        the uncertainty on the line center.
    """
    if return_uncertainty is None:
        return_uncertainty = dy is not None
    popt, cvar = fit_gaussian(x, y, dy, return_uncertainty=True)
    if np.isfinite(popt[0]):
        return (popt[0], cvar[0]) if return_uncertainty else popt[0]
    return (fill, fill) if return_uncertainty else fill


def get_gaussthick_center(x, y, dy=None, return_uncertainty=None, fill=1e50):
    """
    Return the line center from an optically thick Gaussian fit to the spectrum.

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.
        fill (Optional[float]): Values to return if the fit fails.

    Returns:
        popt (array)[, cvar(array)]: The best fit line center and, optionally,
        the uncertainty on the line center.
    """
    if return_uncertainty is None:
        return_uncertainty = dy is not None
    popt, cvar = fit_gaussian_thick(x, y, dy, return_uncertainty=True)
    if np.isfinite(popt[0]):
        return (popt[0], cvar[0]) if return_uncertainty else popt[0]
    return (fill, fill) if return_uncertainty else fill


def get_doublegauss_center(x, y, dy=None, return_uncertainty=None, fill=1e50):
    """
    Return the line center from a fit of two Gaussians to the spectrum. The line
    center will be of the component with the largest amplitude.

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.
        fill (Optional[float]): Values to return if the fit fails.

    Returns:
        popt (array)[, cvar(array)]: The best fit line center and, optionally,
        the uncertainty on the line center.
    """
    if return_uncertainty is None:
        return_uncertainty = dy is not None
    popt, cvar = fit_double_gaussian(x, y, dy, return_uncertainty=True)
    if np.isfinite(popt[2]) and np.isfinite(popt[5]):
        return (popt[0], cvar[0]) if return_uncertainty else popt[0]
    else:
        return (fill, fill) if return_uncertainty else fill


def get_doublegauss_fixeddV_center(x, y, dy=None, return_uncertainty=None,
                                   fill=1e50):
    """
    Return the line center from a fit of two Gaussians which share a width to
    the spectrum. The line  center will be of the component with the largest
    amplitude.

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.
        fill (Optional[float]): Values to return if the fit fails.

    Returns:
        popt (array)[, cvar(array)]: The best fit line center and, optionally,
        the uncertainty on the line center.
    """
    if return_uncertainty is None:
        return_uncertainty = dy is not None
    popt, cvar = fit_double_gaussian_fixeddV(x, y, dy, return_uncertainty=True)
    if np.isfinite(popt[2]) and np.isfinite(popt[4]):
        return (popt[0], cvar[0]) if return_uncertainty else popt[0]
    else:
        return (fill, fill) if return_uncertainty else fill


def get_gaussian_width(x, y, dy=None, return_uncertainty=None, fill=1e50):
    """
    Return the absolute width of a Gaussian fit to the spectrum.

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.
        dy (Optional[array]): Uncertainties on data.
        return_uncertainty (Optional[bool]): Whether to return uncertainties.
        fill (Optional[float]): Values to return if the fit fails.

    Returns:
        popt (array)[, cvar(array)]: The best fit line width and, optionally,
        the uncertainty on the line width.
    """
    if return_uncertainty is None:
        return_uncertainty = dy is not None
    popt, cvar = fit_gaussian(x, y, dy, return_uncertainty=True)
    if np.isfinite(popt[1]):
        return (popt[1], cvar[1]) if return_uncertainty else popt[1]
    return (fill, fill) if return_uncertainty else fill


def get_p0_gaussian(x, y):
    """
    Estimate (x0, dV, Tb) for the spectrum.

    Args:
        x (array): Dependent coordinate.
        y (array): Data coordinate.

    Returns:
        p0 (array): Estimate (x0, dV, Tb) values for the provided data.
    """
    if x.size != y.size:
        raise ValueError("Mismatch in array shapes.")
    Tb = np.max(y)
    x0 = x[y.argmax()]
    dV = np.trapz(y, x) / Tb / np.sqrt(2. * np.pi)
    return x0, dV, Tb


# -- MODEL FUNCTIONS --#

def gaussian(x, x0, dV, Tb):
    """Gaussian function."""
    return Tb * np.exp(-np.power((x - x0) / dV, 2.0))


def gaussian_thick(x, x0, dV, Tex, tau0):
    """Optically thick Gaussian line."""
    tau = gaussian(x, x0, dV, tau0)
    return Tex * (1. - np.exp(-tau))


def double_gaussian_sum(x, x0, dV0, Tb0, x1, dV1, Tb1):
    """Double Gaussian profile as sum of two Gaussians."""
    return gaussian(x, x0, dV0, Tb0) + gaussian(x, x1, dV1, Tb1)


def double_gaussian_max(x, x0, dV0, Tb0, x1, dV1, Tb1):
    """Double Gaussian profile as the max of two Gaussian components."""
    return np.max([gaussian(x, x0, dV0, Tb0),
                   gaussian(x, x1, dV1, Tb1)], axis=0)


def double_gaussian_sum_fixeddV(x, x0, dV, Tb0, x1, Tb1):
    """Double Gaussian profile as the sum of two Gaussians with same dV."""
    return gaussian(x, x0, dV, Tb0) + gaussian(x, x1, dV, Tb1)


def double_gaussian_max_fixeddV(x, x0, dV, Tb0, x1, Tb1):
    """Double Gaussian profile as the max of two Gaussian components."""
    return np.max([gaussian(x, x0, dV, Tb0),
                   gaussian(x, x1, dV, Tb1)], axis=0)


def SHO(x, A, C):
    """Simple harmonic oscillator."""
    return A * np.cos(x) + C


def SHO_offset(x, A, B, C):
    """Simple harmonic oscillator with offset."""
    return A * np.cos(x + B) + C


def SHO_double(x, A, B, C):
    """Two orthogonal simple harmonic oscillators."""
    return A * np.cos(x) + B * np.sin(x) + C


# -- PLOTTING FUNCTIONS -- #

def plot_walkers(samples, nburnin=None, labels=None, histogram=True):
    """
    Plot the walkers to check if they are burning in.

    Args:
        samples (ndarray):
        nburnin (Optional[int])
    """

    # Check the length of the label list.

    if labels is not None:
        if samples.shape[0] != len(labels):
            raise ValueError("Not correct number of labels.")

    # Cycle through the plots.

    for s, sample in enumerate(samples):
        fig, ax = plt.subplots()
        for walker in sample.T:
            ax.plot(walker, alpha=0.1, color='k')
        ax.set_xlabel('Steps')
        if labels is not None:
            ax.set_ylabel(labels[s])
        if nburnin is not None:
            ax.axvline(nburnin, ls=':', color='r')

        # Include the histogram.

        if histogram:
            fig.set_size_inches(1.37 * fig.get_figwidth(),
                                fig.get_figheight(), forward=True)
            ax_divider = make_axes_locatable(ax)
            bins = np.linspace(ax.get_ylim()[0], ax.get_ylim()[1], 50)
            hist, _ = np.histogram(sample[nburnin:].flatten(), bins=bins,
                                   density=True)
            bins = np.average([bins[1:], bins[:-1]], axis=0)
            ax1 = ax_divider.append_axes("right", size="35%", pad="2%")
            ax1.fill_betweenx(bins, hist, np.zeros(bins.size), step='mid',
                              color='darkgray', lw=0.0)
            ax1.set_ylim(ax.get_ylim()[0], ax.get_ylim()[1])
            ax1.set_xlim(0, ax1.get_xlim()[1])
            ax1.set_yticklabels([])
            ax1.set_xticklabels([])
            ax1.tick_params(which='both', left=0, bottom=0, top=0, right=0)
            ax1.spines['right'].set_visible(False)
            ax1.spines['bottom'].set_visible(False)
            ax1.spines['top'].set_visible(False)


def plot_corner(samples, labels=None, quantiles=[0.16, 0.5, 0.84]):
    """
    A wrapper for DFM's corner plots.

    Args:
        samples (ndarry):
        labels (Optional[list]):
        quantiles (Optional[list]): Quantiles to use for plotting.
    """
    import corner
    corner.corner(samples, labels=labels, title_fmt='.4f', bins=30,
                  quantiles=quantiles, show_titles=True)

# -- TRANSFORMATION MATRIX FUNCTIONS -- #

def apply_matrix2d_s(p0, warp, twist):
    
    x = p0[:, :, 0]
    y = p0[:, :, 1]
    z = p0[:, :, 2]

    warp = warp[:, None]
    twist = twist[:, None]

    cosw = np.cos(warp)
    sinw = np.sin(warp)
    
    cost = np.cos(-twist)
    sint = np.sin(-twist)
    
    xp = x*cost - y*sint*cosw + z*sint*sinw
    yp = x*sint + y*cost*cosw - z*sinw*cost
    zp = y*sinw + z*cosw

    return np.moveaxis([xp, yp, zp], 0, 2)


def apply_matrix2d_d(p0, warp, twist, inc_, PA_):
    x = p0[:, :, 0]
    y = p0[:, :, 1]
    z = p0[:, :, 2]

    warp = warp[:, None]
    twist = twist[:, None]

    cosw = np.cos(warp)
    sinw = np.sin(warp)

    cost = np.cos(twist)
    sint = np.sin(twist)

    cosPA = np.cos(PA_)
    sinPA = np.sin(PA_)

    cosi = np.cos(inc_)
    sini = np.sin(inc_)

    xp = x*(-sinPA*sint*cosi + cosPA*cost) + y*((-sinPA*cosi*cost - sint*cosPA)*cosw + sinPA*sini*sinw) + z*(-(-sinPA*cosi*cost - sint*cosPA)*sinw + sinPA*sini*cosw)
    yp = x*(sinPA*cost + sint*cosPA*cosi) + y*((-sinPA*sint + cosPA*cosi*cost)*cosw - sini*sinw*cosPA) + z*(-(-sinPA*sint + cosPA*cosi*cost)*sinw - sini*cosPA*cosw)
    zp = x*sini*sint + y*(sini*cost*cosw + sinw*cosi) + z*(-sini*sinw*cost + cosi*cosw)

    return np.moveaxis([xp, yp, zp], 0, 2)

def get_surface(r_i, r0=1.0, z0=0.0, psi=1.25, r_taper=80.0, q_taper=1.5, nphi=50):

    nr = len(r_i) - 1

    # define cylindrical radius, azimuthal angle, and height above mid plane
    ri = np.ones([nr + 1, nphi + 1]) * r_i[:, None]
    phii = np.ones([nr + 1, nphi + 1]) * np.linspace(0, 2 * np.pi, nphi + 1)
    zi = surface(ri, r0=r0, z0=z0, psi=psi, r_taper=r_taper, q_taper=q_taper)

    # define centers as well
    rc = 0.5 * (ri[1:, 1:] + ri[:-1, 1:])
    zc = surface(rc, r0=r0, z0=z0, psi=psi, r_taper=r_taper, q_taper=q_taper)
    phic = 0.5 * (phii[1:, 1:] + phii[1:, :-1])

    # convert to cartesian (x, y = edges, xc, yc = centers)

    xi = ri * np.cos(phii)
    yi = ri * np.sin(phii)

    xc = rc * np.cos(phic)
    yc = rc * np.sin(phic)

    points_i = np.moveaxis([xi, yi, zi], 0, 2)
    points_c = np.moveaxis([xc, yc, zc], 0, 2)

    return {
        'nr': nr,
        'nphi': nphi,
        'points_i': points_i,
        'points_c': points_c,
        'ri': ri,
        'rc': rc,
        'phii': phii,
        'phic': phic
    }

def surface(r, r0=1.0, z0=0.0, psi=1.25, r_taper=80.0, q_taper=1.5):
    """return a surface height `z(r)`.

    Parameters
    ----------
    r : array
        radial grid
    r0 : float, optional
        normalization radius, by default = 1.0
    z0 : float, optional
        surface height normalization at r=r0, by default 0.0
    psi : float, optional
        flaring exponent, by default 1.25
    r_taper : float, optional
        radius where the surface is tapered down, by default 80.0
    q_taper : float, optional
        tapering exponent, by default 1.5

    Returns
    -------
    array
        surface height for each radius in `r`
    """
    return np.clip(z0 * (r / r0) ** psi * np.exp(-(r / r_taper)**q_taper), a_min=0.0, a_max=None)