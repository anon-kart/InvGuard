/*
 * @source: https://github.com/trailofbits/not-so-smart-contracts/blob/master/unprotected_function/Unprotected.sol
 * @author: -
 * @vulnerable_at_lines: 25
 */

 pragma solidity ^0.4.15;

 contract Unprotected{
     address private owner;

     modifier onlyowner {
         require(msg.sender==owner);
         _;
     }

     function Unprotected()
         public
     {
         owner = msg.sender;
     }

     // This function should be protected
     // <yes> <report> ACCESS_CONTROL
     function changeOwner(address _newOwner)
         public
     {
        require(msg.sender==owner);
        owner = _newOwner;
     }

    /*
    function changeOwner_fixed(address _newOwner)
         public
         onlyowner
     {
        owner = _newOwner;
     }
     */
 }


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `Unprotected` has a no-arg constructor (or implicit constructor).
contract Target is Unprotected {
    constructor() Unprotected() {}
}
